import argparse
import os
import sys
import re
import json
import subprocess
import shutil

def parse_args():
    p = argparse.ArgumentParser(
        description="Typedefinition.xml에서 문자열을 검색합니다."
    )

    p.add_argument("config_path", help="config.json 경로")
    p.add_argument("--run-deploy", action="store_true", help="nexacroDeployExecute를 실행합니다")

    p.add_argument("-i", "--ignore-case", action="store_true", help="대소문자 무시")
    p.add_argument("--contains-only", action="store_true", help="라인 전체 출력 대신 '발견 여부'만 표시")
    p.add_argument("--max-hits", type=int, default=0, help="최대 출력 개수(0이면 제한 없음)")
    p.add_argument("--encoding", default="utf-8", help="파일 인코딩(기본 utf-8)")
    p.add_argument("--errors", default="ignore", choices=["ignore", "replace", "strict"],
                   help="디코딩 에러 처리(기본 ignore)")
    p.add_argument("--no-line-number", action="store_true", help="줄번호 출력하지 않음")

    return p.parse_args()

def load_config(config_path: str) -> dict:
    if not os.path.isfile(config_path):
        print("config.json 파일을 찾을 수 없습니다:", config_path)
        sys.exit(2)

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as exc:
        print("config.json 파싱에 실패했습니다:", exc)
        sys.exit(2)

def resolve_config_path_value(config_path: str, value: str) -> str:
    """config.json 값이 상대경로면 config.json 위치 기준으로 절대경로로 바꾼다."""
    if not isinstance(value, str) or not value.strip():
        return value
    if os.path.isabs(value):
        return os.path.normpath(value)
    return os.path.normpath(os.path.join(os.path.dirname(config_path), value))

def get_required_config_value(config: dict, key: str) -> str:
    v = config.get(key)
    if not isinstance(v, str) or not v.strip():
        print(f'config.json에 "{key}" 값이 없거나 올바르지 않습니다.')
        sys.exit(2)
    return v

def load_base_dir_from_F(config: dict, config_path: str) -> str:
    """
    -F를 기준 경로로 사용.
    -F가 파일이면 그 파일의 디렉토리로, 폴더면 폴더 그대로.
    """
    f_val = get_required_config_value(config, "-F")
    f_val = resolve_config_path_value(config_path, f_val)

    if os.path.isfile(f_val):
        return os.path.dirname(f_val)
    return f_val

def build_deploy_base_command(config: dict, config_path: str) -> tuple[list[str], str]:
    """
    -O와 -GENERATERULE은 여기서 넣지 않는다.
    (요구사항: -O는 Services에서 찾은 상대경로와 결합한 값으로 매번 바뀜)
    """
    exe_path = get_required_config_value(config, "nexacroDeployExecute")
    exe_path = resolve_config_path_value(config_path, exe_path)

    p_val = resolve_config_path_value(config_path, get_required_config_value(config, "-P"))
    b_val = resolve_config_path_value(config_path, get_required_config_value(config, "-B"))
    rule_val = resolve_config_path_value(config_path, get_required_config_value(config, "-GENERATERULE"))

    return ([
        exe_path,
        "-P", p_val,
        "-B", b_val,
        # "-O", <여기서 넣지 않음>
        # "-GENERATERULE", <여기서 넣지 않음>
    ], rule_val)

def search_rel_paths_in_services_block(
    file_path: str,
    encoding: str,
    errors: str,
    contains_only: bool,
    max_hits: int,
) -> tuple[int, list[str]]:
    """
    typedefinition.xml의 <Services>...</Services> 구간 내부에서 ../로 시작하는 상대 경로 토큰만 수집
    """
    if not os.path.isfile(file_path):
        print("파일이 존재하지 않습니다:", file_path)
        return 2, []

    hits = 0
    rel_paths: list[str] = []

    rel_path_pattern = re.compile(r"\.\./[^\"'\s<>]+")
    open_services = re.compile(r"<\s*Services\b", re.IGNORECASE)
    close_services = re.compile(r"</\s*Services\s*>", re.IGNORECASE)

    in_services = False

    with open(file_path, "r", encoding=encoding, errors=errors) as f:
        for line in f:
            if not in_services and open_services.search(line):
                in_services = True

            if in_services:
                matches = rel_path_pattern.findall(line)
                if matches:
                    for m in matches:
                        hits += 1

                        if contains_only:
                            if hits == 1:
                                print("문구 발견!")
                            if max_hits > 0 and hits >= max_hits:
                                break
                            continue

                        rel_paths.append(m)

                        if max_hits > 0 and hits >= max_hits:
                            break

                    if max_hits > 0 and hits >= max_hits:
                        break

            if in_services and close_services.search(line):
                in_services = False

    return (0 if hits > 0 else 1), rel_paths

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

    for rp in rel_paths:
        eff = os.path.normpath(os.path.join(base_o, rp))
        if eff not in seen:
            seen.add(eff)
            o_values.append(eff)

    return o_values

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

    for rp in rel_paths:
        target = os.path.normpath(os.path.join(base_f_dir, rp))

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

def run_nexacro_deploy_repeat(config: dict, config_path: str, effective_o_list: list[str], file_paths: list[str]) -> None:
    """
    실행 정책(요구사항 3: 현재 실행 방식 유지):
    - 기본 옵션은 고정
    - -O는 effective_o_list의 값으로 순회(= Services 토큰 기반으로 재설정)
    - 각 -O에 대해, -FILE은 file_paths의 파일 개수만큼 반복 실행
    - 변하는 건 -O와 -FILE뿐이며, 그 외(-P -B -GENERATERULE)는 고정
    """
    base_cmd, rule_val = build_deploy_base_command(config, config_path)

    if not effective_o_list:
        print("실행할 -O 대상이 없습니다. (Services에서 상대경로 토큰을 찾지 못함)")
        sys.exit(1)

    if not file_paths:
        print("실행할 -FILE 대상 파일이 없습니다. (-F 기준 폴더에서 .xfdl/.xjs 파일을 찾지 못함)")
        sys.exit(1)

    for eff_o in effective_o_list:
        for fp in file_paths:
            cmd = base_cmd + ["-O", eff_o, "-GENERATERULE", rule_val, "-FILE", fp]
            print("\n[RUN]", " ".join(f'"{c}"' if " " in c else c for c in cmd))
            result = subprocess.run(cmd, check=False)
            if result.returncode != 0:
                print("nexacroDeployExecute 실행에 실패했습니다. 종료 코드:", result.returncode)
                sys.exit(result.returncode)
            move_js_files_from_file_dir(fp, eff_o)

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

        dest_dir = os.path.dirname(dest_path)
        if dest_dir:
            os.makedirs(dest_dir, exist_ok=True)

        if os.path.exists(dest_path):
            os.remove(dest_path)

        shutil.move(src_path, dest_path)

def main():
    args = parse_args()
    config = load_config(args.config_path)

    # typedefinition.xml 위치는 -F 기준 (기존 철학 유지)
    base_dir = load_base_dir_from_F(config, args.config_path)
    xml_path = os.path.join(base_dir, "typedefinition.xml")
    if not os.path.isfile(xml_path):
        print("typedefinition.xml 파일을 찾을 수 없습니다:", xml_path)
        sys.exit(2)

    # 1) Services 구간에서 ../상대경로 토큰 수집
    exit_code, rel_paths = search_rel_paths_in_services_block(
        file_path=xml_path,
        encoding=args.encoding,
        errors=args.errors,
        contains_only=args.contains_only,
        max_hits=args.max_hits,
    )

    if args.contains_only:
        sys.exit(exit_code)

    # 2) -O는 (-O + token) 결합으로 재설정된 값 목록
    effective_o_list = compute_effective_O_values(config, args.config_path, rel_paths)

    # 3) -FILE은 -F 기준으로 펼친 파일 목록
    file_paths = collect_files_for_FILE_from_F(config, args.config_path, rel_paths)

    # 4) --run-deploy면 현재 실행 방식 유지하며 반복 실행
    if args.run_deploy:
        run_nexacro_deploy_repeat(config, args.config_path, effective_o_list, file_paths)

    sys.exit(exit_code)

if __name__ == "__main__":
    main()
