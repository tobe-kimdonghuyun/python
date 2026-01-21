import argparse
import os
import sys
import re
import json
import subprocess

def parse_args():
    p = argparse.ArgumentParser(
        description="Typedefinition.xml에서 문자열을 검색합니다."
    )

    p.add_argument("config_path", help="config.json 경로")
    p.add_argument("--run-deploy", action="store_true", help="nexacroDeployExecute를 실행합니다")
    # (기존 옵션들은 유지)
    p.add_argument("-i", "--ignore-case", action="store_true", help="대소문자 무시")
    p.add_argument("--contains-only", action="store_true", help="라인 전체 출력 대신 '발견 여부'만 표시")
    p.add_argument("--max-hits", type=int, default=0, help="최대 출력 개수(0이면 제한 없음)")
    p.add_argument("--encoding", default="utf-8", help="파일 인코딩(기본 utf-8)")
    p.add_argument("--errors", default="ignore", choices=["ignore", "replace", "strict"],help="디코딩 에러 처리(기본 ignore)")    
    p.add_argument("--no-line-number", action="store_true",help="줄번호 출력하지 않음")

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

def load_base_dir(config: dict, config_path: str) -> str:
    base_dir = config.get("-F")
    if not isinstance(base_dir, str) or not base_dir.strip():
        print('config.json에 "-F" 값이 없거나 올바르지 않습니다.')
        sys.exit(2)

    if not os.path.isabs(base_dir):
        base_dir = os.path.normpath(
            os.path.join(os.path.dirname(config_path), base_dir)
        )

    if os.path.isfile(base_dir):
        base_dir = os.path.dirname(base_dir)

    return base_dir

def run_nexacro_deploy(config: dict, config_path: str) -> None:
    exe_path = config.get("nexacroDeployExecute")
    if not isinstance(exe_path, str) or not exe_path.strip():
        print('config.json에 "nexacroDeployExecute" 값이 없거나 올바르지 않습니다.')
        sys.exit(2)

    required_keys = ["-P", "-O", "-B", "-GENERATERULE"]
    values: dict[str, str] = {}
    for key in required_keys:
        value = config.get(key)
        if not isinstance(value, str) or not value.strip():
            print(f'config.json에 "{key}" 값이 없거나 올바르지 않습니다.')
            sys.exit(2)
        values[key] = value

    if not os.path.isabs(exe_path):
        exe_path = os.path.normpath(
            os.path.join(os.path.dirname(config_path), exe_path)
        )

    command = [
        exe_path,
        "-P", values["-P"],
        "-O", values["-O"],
        "-B", values["-B"],
        "-GENERATERULE", values["-GENERATERULE"],
    ]

    result = subprocess.run(command, check=False)
    if result.returncode != 0:
        print("nexacroDeployExecute 실행에 실패했습니다. 종료 코드:", result.returncode)
        sys.exit(result.returncode)

def search_in_services_block(file_path: str, ignore_case: bool,
                             encoding: str, errors: str,
                             contains_only: bool, max_hits: int,
                             base_dir: str) -> tuple[int, list[list[str]]]:
    """
    typedefinition.xml의 <Services>...</Services> 구간 내부에서 ../로 시작하는
    상대 경로 토큰들을 찾아 출력한다.
    """
    if not os.path.isfile(file_path):
        print("파일이 존재하지 않습니다:", file_path)
        return 2

    hits = 0
    saved_paths: list[list[str]] = []
    # ../로 시작하는 경로 토큰 추출 (따옴표/공백/태그 경계에서 끊김)
    rel_path_pattern = re.compile(r"\.\./[^\"'\s<>]+")

    # Services 구간 판별 (대소문자 무시)
    open_services = re.compile(r"<\s*Services\b", re.IGNORECASE)
    close_services = re.compile(r"</\s*Services\s*>", re.IGNORECASE)

    in_services = False

    seen_paths = set()
    allowed_extensions = {".xfdl", ".xjs"}

    def is_allowed_file(name: str) -> bool:
        return os.path.splitext(name)[1].lower() in allowed_extensions

    def describe_files(target_path: str) -> None:
        if target_path in seen_paths:
            return
        seen_paths.add(target_path)

        if not os.path.exists(target_path):
            print("경로가 존재하지 않습니다:", target_path)
            return

        if os.path.isfile(target_path):
            print(target_path)
            if is_allowed_file(target_path):
                saved_paths.append([target_path])
                print("파일 개수: 1")
                print("파일명:", os.path.basename(target_path))
            else:
                print("파일 개수: 0")
                print("파일명: 없음")
            return

        files = [
            name for name in os.listdir(target_path)
            if os.path.isfile(os.path.join(target_path, name))
            and is_allowed_file(name)
        ]
        files.sort()
        if files:
            combined_paths = [target_path] + [
                os.path.join(target_path, name) for name in files
            ]
            saved_paths.append(combined_paths)
        print(target_path)
        print(f"파일 개수: {len(files)}")
        if files:
            print("파일명:", ", ".join(files))
        else:
            print("파일명: 없음")

    with open(file_path, "r", encoding=encoding, errors=errors) as f:
        for line in f:
            # 구간 시작 감지
            if not in_services and open_services.search(line):
                in_services = True

            # Services 구간 내부만 처리
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

                        combined = os.path.normpath(os.path.join(base_dir, m))
                        if m.endswith(("/", "\\")):
                            combined = f"{combined}{os.sep}"
                        describe_files(combined)

                        if max_hits > 0 and hits >= max_hits:
                            break

                    if max_hits > 0 and hits >= max_hits:
                        break

            # 구간 종료 감지 (이 줄 처리 후 닫히는 형태도 대응)
            if in_services and close_services.search(line):
                in_services = False

    return (0 if hits > 0 else 1), saved_paths

def main():
    args = parse_args()

    config = load_config(args.config_path)

    if args.run_deploy:
        run_nexacro_deploy(config, args.config_path)

    base_dir = load_base_dir(config, args.config_path)

    xml_path = os.path.join(base_dir, "typedefinition.xml")
    if not os.path.isfile(xml_path):
        print("typedefinition.xml 파일을 찾을 수 없습니다:", xml_path)
        sys.exit(2)

    exit_code, saved_paths = search_in_services_block(
        file_path=xml_path,
        ignore_case=args.ignore_case,
        encoding=args.encoding,
        errors=args.errors,
        contains_only=args.contains_only,
        max_hits=args.max_hits,
        base_dir=base_dir
    )
    sys.exit(exit_code)

if __name__ == "__main__":
    main()
