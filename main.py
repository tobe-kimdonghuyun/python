import argparse
import sys
import os
from core.config_manager import load_config, load_base_dir_from_F, resolve_config_path_value, get_required_config_value
from core.xml_parser import search_rel_paths_in_services_block
from core.file_utils import compute_effective_O_values, collect_files_for_FILE_from_F
from core.deploy_manager import run_phase1_project_deploy, run_phase2_file_deploy, cleanup_test_files

def parse_args():
    """
    커맨드 라인 인자를 파싱합니다.
    
    Returns:
        Namespace: 파싱된 인자 객체
    """
    p = argparse.ArgumentParser(
        description="Typedefinition.xml에서 문자열을 검색하고 배포를 수행합니다. (Refactored Version)"
    )

    p.add_argument("config_path", help="config.json 파일의 경로")
    p.add_argument("--run-deploy", action="store_true", help="설정된 배포 명령(nexacroDeployExecute)을 실행할지 여부")

    p.add_argument("-i", "--ignore-case", action="store_true", help="검색 시 대소문자 무시")
    p.add_argument("--contains-only", action="store_true", help="상세 라인 출력 대신 '문구 발견' 여부만 출력")
    p.add_argument("--max-hits", type=int, default=0, help="최대 검색 출력 개수 제한 (0이면 제한 없음)")
    p.add_argument("--encoding", default="utf-8", help="파일 읽기 인코딩 (기본값: utf-8)")
    p.add_argument("--errors", default="ignore", choices=["ignore", "replace", "strict"],help="인코딩 에러 처리 방식 (기본값: ignore)")
    p.add_argument("--no-line-number", action="store_true", help="출력 시 줄번호 생략")
    p.add_argument("--test", action="store_true", help="테스트 모드 (실행 후 생성 파일 삭제)")

    return p.parse_args()

def main():
    """
    메인 실행 함수. 전반적인 로직 흐름을 제어합니다.
    1. 설정 로드
    2. XML 파싱 (경로 토큰 수집)
    3. 배포 경로 및 대상 파일 계산
    4. 배포 명령 실행 (Phase 1 -> Phase 2)
    """
    args = parse_args()
    config = load_config(args.config_path)

    # typedefinition.xml 위치는 -F 설정값 기준으로 파악 (기존 로직 유지)
    base_dir = load_base_dir_from_F(config, args.config_path)
    xml_path = os.path.join(base_dir, "typedefinition.xml")
    
    if not os.path.isfile(xml_path):
        print("typedefinition.xml 파일을 찾을 수 없습니다:", xml_path)
        sys.exit(2)

    # 1) Typedefinition.xml의 <Services> 구간에서 ../ 로 시작하는 상대 경로 패턴 수집
    exit_code, rel_paths = search_rel_paths_in_services_block(
        file_path=xml_path,
        encoding=args.encoding,
        errors=args.errors,
        contains_only=args.contains_only,
        max_hits=args.max_hits,
    )

    # --contains-only 옵션이 켜져있으면 단순히 발견 여부만 체크하고 종료
    if args.contains_only:
        sys.exit(exit_code)

    # 2) -O 옵션 값과 수집된 토큰을 결합하여 실제 배포 대상 폴더 리스트 생성
    d_val = config.get("-D")
    base_deploy_path = None
    if d_val and isinstance(d_val, str) and d_val.strip():
        base_deploy_path = resolve_config_path_value(args.config_path, d_val)

    effective_o_map = compute_effective_O_values(config, args.config_path, rel_paths, base_path=base_deploy_path)

    # 3) -F 기준 폴더와 상대 경로를 결합하여 실제 배포할 파일(.xfdl, .xjs) 리스트 생성
    file_paths_by_rel = collect_files_for_FILE_from_F(config, args.config_path, rel_paths)

    # 4) 배포 실행 (Phase 1 -> Phase 2)
    run_phase1_project_deploy(config, args.config_path, effective_o_map)
    run_phase2_file_deploy(config, args.config_path, effective_o_map, file_paths_by_rel)

    # 5) 테스트 모드일 경우 정리
    if args.test:
        cleanup_targets = list(effective_o_map.values())
        base_o_param = get_required_config_value(config, "-O")
        base_o = resolve_config_path_value(args.config_path, base_o_param)
        
        if base_deploy_path and base_deploy_path not in cleanup_targets:
            cleanup_targets.append(base_deploy_path)
        if base_o not in cleanup_targets:
            cleanup_targets.append(base_o)
            
        cleanup_test_files(cleanup_targets)

    sys.exit(exit_code)

if __name__ == "__main__":
    main()
