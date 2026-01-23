import argparse
import os
import sys
import re
import json
import subprocess
import shutil
from core.file_utils import compute_effective_O_values, collect_files_for_FILE_from_F, move_js_files_from_file_dir
from core.config_manager import resolve_config_path_value, get_required_config_value, load_base_dir_from_F, load_config

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
    p.add_argument("--test", action="store_true", help="테스트 모드 (실행 후 생성 파일 삭제)")

    return p.parse_args()


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

    d_val = config.get("-D")
    if d_val and isinstance(d_val, str) and d_val.strip():
        d_val = resolve_config_path_value(config_path, d_val)
        base_cmd_list = [
            exe_path,
            "-P", p_val,
            "-B", b_val,
            "-D", d_val,
        ]
    else:
        base_cmd_list = [
            exe_path,
            "-P", p_val,
            "-B", b_val,
        ]

    # -COMPRESS 옵션 처리 (boolean)
    if config.get("-COMPRESS") is True:
        base_cmd_list.append("-COMPRESS")

    # -SHRINK 옵션 처리 (boolean)
    if config.get("-SHRINK") is True:
        base_cmd_list.append("-SHRINK")

    return (base_cmd_list, rule_val)

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


def run_phase1_project_deploy(
    config: dict,
    config_path: str,
    effective_o_map: dict[str, str]
) -> None:
    """
    Phase 1: 프로젝트 단위 배포 실행 (파일 지정 없이)
    Requirement: 1단계에서는 -P, -O, -B, -GENERATERULE 및 설정된 옵션(-D, -COMPRESS, -SHRINK)들을 사용하여 전체 프로젝트 배포
    """
    base_cmd, rule_val = build_deploy_base_command(config, config_path)
    
    # config.json의 -O 값 그대로 가져오기
    base_o = resolve_config_path_value(config_path, get_required_config_value(config, "-O"))

    print("\n[Phase 1] Project Deploy")
    # 1단계는 한 번만 실행하면 됨 (전체 프로젝트 배포)
    cmd = base_cmd + ["-O", base_o, "-GENERATERULE", rule_val]
    
    print(f"[RUN] {' '.join(cmd)}")
    result = subprocess.run(cmd, check=False)
    if result.returncode != 0:
        print("Phase 1 배포 실패. 종료 코드:", result.returncode)
        sys.exit(result.returncode)

def run_phase2_file_deploy(
    config: dict,
    config_path: str,
    effective_o_map: dict[str, str],
    file_paths_by_rel: dict[str, list[str]]
) -> None:
    """
    Phase 2: 파일 단위 배포 및 JS 이동
    Requirement: -P, -O, -B, -GENERATERULE, -FILE 및 설정된 옵션으로 nexacrodeploy.exe 실행
    이후 move_js_files_from_file_dir 작업 진행
    """
    base_cmd, rule_val = build_deploy_base_command(config, config_path)

    if not effective_o_map:
        print("실행할 -O 대상이 없습니다. (Services에서 상대경로 토큰을 찾지 못함)")
        sys.exit(1)

    if not file_paths_by_rel:
        print("실행할 -FILE 대상 파일이 없습니다. (-F 기준 폴더에서 .xfdl/.xjs 파일을 찾지 못함)")
        sys.exit(1)

    print("\n[Phase 2] File Deploy")
    for rel_path, eff_o in effective_o_map.items():
        files = file_paths_by_rel.get(rel_path, [])
        if not files:
            continue
            
        for fp in files:
            # -FILE 추가
            cmd = base_cmd + ["-O", eff_o, "-GENERATERULE", rule_val, "-FILE", fp]
            
            print(f"[RUN] {' '.join(cmd)}")
            result = subprocess.run(cmd, check=False)
            if result.returncode != 0:
                print(f"Phase 2 배포 실패 ({fp}). 종료 코드:", result.returncode)
                sys.exit(result.returncode)
            
            # 배포 후 생성된 js 파일을 올바른 위치로 이동
            move_js_files_from_file_dir(fp, eff_o)

def cleanup_test_files(created_dirs: list[str]) -> None:
    """
    테스트 종료 후 생성된 폴더/파일 정리
    """
    print("\n[CLEANUP] 테스트 생성 파일 삭제 중...")
    for d in created_dirs:
        if os.path.exists(d):
            try:
                shutil.rmtree(d)
                print(f"삭제됨: {d}")
            except Exception as e:
                print(f"삭제 실패: {d} - {e}")

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
    # Requirements: -D 옵션이 있으면 -D 경로를 기준으로 상대경로 결합 (Phase 2용)
    d_val = config.get("-D")
    base_deploy_path = None
    has_d_option = False
    
    if d_val and isinstance(d_val, str) and d_val.strip():
        has_d_option = True
        base_deploy_path = resolve_config_path_value(args.config_path, d_val)

    # Phase 2에서 사용할 effective_o_map 계산
    # -D가 있으면 base_deploy_path(-D값)를 사용, 없으면 -O값 사용
    effective_o_map = compute_effective_O_values(config, args.config_path, rel_paths, base_path=base_deploy_path)

    # 3) -FILE은 -F 기준으로 펼친 파일 목록
    file_paths_by_rel = collect_files_for_FILE_from_F(config, args.config_path, rel_paths)

    # 4) 실행 전략: 무조건 1단계(Project) -> 2단계(File) 순서로 실행
    run_phase1_project_deploy(config, args.config_path, effective_o_map)
    run_phase2_file_deploy(config, args.config_path, effective_o_map, file_paths_by_rel)

    # 5) 테스트 모드일 경우 정리
    if args.test:
        cleanup_targets = list(effective_o_map.values())
        
        base_o_param = get_required_config_value(config, "-O")
        base_o = resolve_config_path_value(args.config_path, base_o_param)
        
        if base_deploy_path:
             if base_deploy_path not in cleanup_targets:
                 cleanup_targets.append(base_deploy_path)
        
        if base_o not in cleanup_targets:
            cleanup_targets.append(base_o)
            
        # 배포된 폴더들 정리
        cleanup_test_files(cleanup_targets)
    
    sys.exit(exit_code)

if __name__ == "__main__":
    main()
