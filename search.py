import argparse
import os
import sys
import re
import json
import subprocess
import shutil

def parse_args():
    """
    커맨드 라인 인자를 파싱하는 함수.
    이 함수는 사용자가 실행 시 입력한 옵션들을 해석하여 반환합니다.

    Returns:
        Namespace: 파싱된 인자 객체 (접근 예: args.config_path)
    """
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
    """
    JSON 설정 파일을 읽어오는 함수.

    Args:
        config_path (str): 읽을 설정 파일(.json)의 경로

    Returns:
        dict: 파싱된 JSON 설정 데이터
    """
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
    """
    config.json 내의 상대 경로 값을 절대 경로로 변환하는 함수.
    설정 파일의 위치가 기준점이 됩니다.

    Args:
        config_path (str): 설정 파일의 경로 (기준 경로)
        value (str): 변환할 경로 문자열

    Returns:
        str: 변환된 절대 경로
    """
    if not isinstance(value, str) or not value.strip():
        return value
    if os.path.isabs(value):
        return os.path.normpath(value)
    return os.path.normpath(os.path.join(os.path.dirname(config_path), value))

def get_required_config_value(config: dict, key: str) -> str:
    """
    필수 설정 값을 가져오는 함수. 값이 없으면 에러를 출력하고 종료합니다.

    Args:
        config (dict): 설정 데이터
        key (str): 가져올 키

    Returns:
        str: 설정 값
    """
    v = config.get(key)
    if not isinstance(v, str) or not v.strip():
        print(f'config.json에 "{key}" 값이 없거나 올바르지 않습니다.')
        sys.exit(2)
    return v

def load_base_dir_from_F(config: dict, config_path: str) -> str:
    """
    '-F' 옵션 값을 기반으로 기준 디렉토리를 결정하는 함수.
    '-F'가 파일을 가리키면 그 파일의 상위 폴더를 기준으로 삼습니다.

    Args:
        config (dict): 설정 데이터
        config_path (str): 설정 파일 경로

    Returns:
        str: 기준 디렉토리 절대 경로
    """
    f_val = get_required_config_value(config, "-F")
    f_val = resolve_config_path_value(config_path, f_val)

    if os.path.isfile(f_val):
        return os.path.dirname(f_val)
    return f_val

def build_deploy_base_command(config: dict, config_path: str) -> tuple[list[str], str]:
    """
    배포 실행에 필요한 기본 명령어와 GENERATERULE 값을 준비하는 함수.
    반복 실행 시 변하지 않는 값들을 미리 구성해 둡니다.
    
    주의: -O(Output)와 -GENERATERULE은 이 함수에서 리스트에 포함하지 않습니다.
    이유는 -O는 동적으로 변경되어야 하고, -GENERATERULE 값은 별도로 관리하기 때문입니다.

    Args:
        config (dict): 설정 데이터
        config_path (str): 설정 파일 경로

    Returns:
        tuple[list[str], str]: (기본 명령어 리스트, GENERATERULE 값 문자열)
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
    typedefinition.xml 파일의 <Services> 태그 내부에서 '../'로 시작하는 상대 경로를 검색하는 핵심 로직.
    
    Args:
        file_path (str): XML 파일 경로
        encoding (str): 인코딩
        errors (str): 에러 처리 방식
        contains_only (bool): 단순 발견 여부만 체크할지 여부
        max_hits (int): 최대 검색 히트 수

    Returns:
        tuple[int, list[str]]: (exit_code, 발견된 상대 경로 리스트)
    """
    if not os.path.isfile(file_path):
        print("파일이 존재하지 않습니다:", file_path)
        return 2, []

    hits = 0
    rel_paths: list[str] = []

    # 정규식 설명: ../ 로 시작하고 따옴표나 공백, 괄호가 나오기 전까지 매칭
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
    Requirements 2:
    설정된 -O(Output) 기본 경로와 XML에서 찾은 상대 경로들을 결합하여,
    실제 배포 결과물이 저장될 폴더 경로들을 계산합니다.

    예: 
    -O 설정값: C:\\Project\\Deploy
    발견된 토큰: ../ModuleA
    결과: C:\\Project\\ModuleA (계산된 절대 경로)
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
    Requirements 1:
    -FILE 인자에 전달할 소스 파일들의 리스트를 수집합니다.
    -F 옵션 값(폴더) 전체에서 .xfdl, .xjs 파일들을 찾습니다.
    """
    del rel_paths
    base_f_dir = load_base_dir_from_F(config, config_path)

    allowed_extensions = {".xfdl", ".xjs"}

    def is_allowed_file(path: str) -> bool:
        return os.path.splitext(path)[1].lower() in allowed_extensions

    out_files: list[str] = []

    for root, _dirs, files in os.walk(base_f_dir):
        for name in files:
            full = os.path.join(root, name)
            if is_allowed_file(full):
                out_files.append(full)

    # 중복 제거 + 정렬
    return sorted(set(out_files))

def run_nexacro_deploy_repeat(config: dict, config_path: str, effective_o_list: list[str], file_paths: list[str]) -> None:
    """
    Requirements 3: 실행 정책 유지
    계산된 배포 경로(-O) 리스트와 파일(-FILE) 리스트를 조합하여
    nexacroDeployExecute 명령을 반복 실행합니다.

    실행 구조:
      Outer Loop: 배포 대상 경로(폴더) 리스트 순회
        Inner Loop: 배포할 소스 파일 리스트 순회
          Command: [BaseCmd] -O [CurrentOutputPath] -GENERATERULE [Rule] -FILE [CurrentSourceFile]
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
            # 배포 후 생성된 js 파일을 올바른 위치로 이동
            move_js_files_from_file_dir(fp, eff_o)

def move_js_files_from_file_dir(file_path: str, o_dir: str) -> None:
    """
    배포 실행 시 생성된 .js 파일들을 정리(이동)하는 함수.
    
    동작:
    1. 원본 파일이 있던 폴더(src_dir)를 탐색
    2. 생성된 .js 파일이 있으면
    3. 목적지 폴더(o_dir, -O 옵션값)로 이동시킴
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
            os.remove(dest_path)# generate가 된 파일이 이동될 위치에 폴더가 없을 경우 생성

        shutil.move(src_path, dest_path)

def main():
    """
    프로그램의 진입점(Entry Point).
    전체적인 실행 흐름을 제어합니다.
    """
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
    # 4) --run-deploy 옵션 여부와 상관없이 실행
    run_nexacro_deploy_repeat(config, args.config_path, effective_o_list, file_paths)

    sys.exit(exit_code)

if __name__ == "__main__":
    main()
