import os
import shutil

from core.config_manager import get_required_config_value, load_base_dir_from_F, resolve_config_path_value


def collect_files_for_FILE_from_F(config: dict, config_path: str, rel_paths: list[str]) -> list[str]:
    """
    요구사항 1:
    -FILE 대상 파일 경로는 -F 기준으로 만든다.
    -F(폴더) + ../mmaMW/gtmd -> 실제 폴더 -> 내부 .xfdl/.xjs 파일을 펼쳐서 반환
    """
    base_f_dir = load_base_dir_from_F(config, config_path)

    allowed_extensions = {".xfdl", ".xjs"}

    def is_allowed_file(path: str) -> bool:
        return os.path.splitext(path)[1].lower() in allowed_extensions

    out_files: list[str] = []
    seen_targets = set()

    for rel_path in rel_paths:
        target = os.path.normpath(os.path.join(base_f_dir, rel_path))

        if target in seen_targets:
            continue
        seen_targets.add(target)

        if not os.path.exists(target):
            print("경로가 존재하지 않습니다:", target)
            continue

        if os.path.isfile(target):
            if is_allowed_file(target):
                out_files.append(target)
            continue

        # 폴더면 내부 파일 펼치기
        for name in os.listdir(target):
            full = os.path.join(target, name)
            if os.path.isfile(full) and is_allowed_file(full):
                out_files.append(full)

    # 중복 제거 + 정렬
    return sorted(set(out_files))


def compute_effective_O_values(config: dict, config_path: str, rel_paths: list[str]) -> list[str]:
    """
    요구사항 2:
    config의 -O + Services에서 찾은 상대경로 토큰을 결합해서
    실제로 실행할 -O 값(폴더)을 만든다.
    예) -O=...\\nexacroCom, token=../mmaMW/gtmd -> ...\\mmaMW\\gtmd
    """
    base_o = resolve_config_path_value(config_path, get_required_config_value(config, "-O"))
    o_values: list[str] = []
    seen = set()

    for rel_path in rel_paths:
        eff = os.path.normpath(os.path.join(base_o, rel_path))
        if eff not in seen:
            seen.add(eff)
            o_values.append(eff)

    return o_values


def move_js_files_from_file_dir(file_path: str, o_dir: str) -> None:
    """
    요구사항:
    -FILE 인자의 마지막 파일명을 제거한 폴더에서 .js 확장자만 찾아
    -O 경로로 이동한다.
    """
    src_dir = os.path.dirname(file_path)
    if not os.path.isdir(src_dir):
        print("원본 폴더가 존재하지 않습니다:", src_dir)
        return

    os.makedirs(o_dir, exist_ok=True)

    for name in os.listdir(src_dir):
        if os.path.splitext(name)[1].lower() != ".js":
            continue

        src_path = os.path.join(src_dir, name)
        if not os.path.isfile(src_path):
            continue

        dest_path = os.path.join(o_dir, name)
        if os.path.abspath(src_path) == os.path.abspath(dest_path):
            continue
        # generate가 된 파일이 이동될 위치에 폴더가 없을 경우 생성
        dest_dir = os.path.dirname(dest_path)
        if dest_dir:
            os.makedirs(dest_dir, exist_ok=True)

        if os.path.exists(dest_path):
            os.remove(dest_path)  # generate가 된 파일이 이동될 위치에 폴더가 없을 경우 생성

        shutil.move(src_path, dest_path)
