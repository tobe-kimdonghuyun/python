import os
import sys
import shutil
from .config_manager import resolve_config_path_value, get_required_config_value

def compute_effective_O_values(config: dict, config_path: str, rel_paths: list[str]) -> dict[str, list[str]]:
    """
    설정 파일의 -O 및 -D 옵션 값과 Services에서 추출한 상대 경로들을 결합하여,
    각 상대 경로별로 실제로 배포 결과물이 저장될 절대 경로 리스트를 생성합니다.
    """
    # 베이스 경로 수집 (-O는 필수, -D는 선택)
    base_paths = []
    
    # -O 베이스
    base_o = resolve_config_path_value(config_path, get_required_config_value(config, "-O"))
    base_paths.append(base_o)
    
    # -D 베이스 (존재할 경우)
    d_val = config.get("-D")
    if d_val and isinstance(d_val, str) and d_val.strip():
        base_d = resolve_config_path_value(config_path, d_val)
        if base_d not in base_paths:
            base_paths.append(base_d)
        
    o_values: dict[str, list[str]] = {}

    for rp in rel_paths:
        norm_rp = os.path.normpath(rp)
        target_list = []
        for bp in base_paths:
            eff = os.path.normpath(os.path.join(bp, rp))
            target_list.append(eff)
        o_values[norm_rp] = target_list
    return o_values

def collect_files_for_FILE_from_P(config: dict, config_path: str, rel_paths: list[str]) -> dict[str, list[str]]:
    """
    -P 파일 위치를 기준으로 소스 파일들을 수집합니다.
    
    Args:
        config (dict): 설정 데이터
        config_path (str): 설정 파일 경로
        rel_paths (list[str]): xml_parser에서 추출한 상대 경로 리스트
        
    Returns:
        dict[str, list[str]]: 상대 경로 -> 배포 대상 파일들의 절대 경로 리스트
    """
    from .config_manager import get_base_dir_from_P
    base_dir = get_base_dir_from_P(config, config_path)

    allowed_extensions = {".xfdl", ".xjs"}

    def is_allowed_file(path: str) -> bool:
        return os.path.splitext(path)[1].lower() in allowed_extensions

    out_files: dict[str, list[str]] = {}
    seen_targets = set()

    for rp in rel_paths:
        norm_rp = os.path.normpath(rp)
        target = os.path.normpath(os.path.join(base_dir, rp))

        if target in seen_targets:
            continue
        seen_targets.add(target)

        if not os.path.exists(target):
            print("경로가 존재하지 않습니다:", target)
            continue
        
        collected: set[str] = set()

        if os.path.isfile(target):
            if is_allowed_file(target):
                collected.add(target)
        else:
            for name in os.listdir(target):
                full = os.path.join(target, name)
                if os.path.isfile(full) and is_allowed_file(full):
                    collected.add(full)

        if collected:
            out_files.setdefault(norm_rp, [])
            out_files[norm_rp].extend(sorted(collected))

    return {rp: sorted(set(files)) for rp, files in out_files.items()}

def move_js_files_from_file_dir(file_path: str, o_dir: str) -> None:
    """
    배포 실행 후 생성된 .js 파일들을 원본 폴더에서 대상 폴더(-O 경로)로 이동시킵니다.
    
    Args:
        file_path (str): 원본 파일 경로 (-FILE 인자로 사용된 값)
        o_dir (str): 이동할 대상 디렉토리 경로 (-O 값)
    """
    src_dir = os.path.dirname(file_path) # 원본 파일이 있는 디렉토리
    if not os.path.isdir(src_dir):
        print("원본 폴더가 존재하지 않습니다:", src_dir)
        return

    # 대상 디렉토리가 없으면 생성
    os.makedirs(o_dir, exist_ok=True)

    for name in os.listdir(src_dir):
        # .js 확장자만 처리
        if os.path.splitext(name)[1].lower() != ".js":
            continue

        src_path = os.path.join(src_dir, name)
        if not os.path.isfile(src_path):
            continue

        dest_path = os.path.join(o_dir, name)
        
        # 원본과 대상이 같은 경우 이동 불필요
        if os.path.abspath(src_path) == os.path.abspath(dest_path):
            continue
            
        # 이동할 위치에 상위 폴더가 없으면 생성
        dest_dir = os.path.dirname(dest_path)
        if dest_dir:
            os.makedirs(dest_dir, exist_ok=True)
            
        # 이미 대상 파일이 존재하면 삭제 (덮어쓰기 준비)
        if os.path.exists(dest_path):
            os.remove(dest_path)

        # 파일 이동
        shutil.move(src_path, dest_path)
