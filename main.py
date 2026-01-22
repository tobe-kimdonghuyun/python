import argparse
import sys
import os
from core.config_manager import load_config, load_base_dir_from_F
from core.xml_parser import search_rel_paths_in_services_block
from core.file_utils import compute_effective_O_values, collect_files_for_FILE_from_F
from core.deploy_manager import run_nexacro_deploy_repeat

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
    p.add_argument("--errors", default="ignore", choices=["ignore", "replace", "strict"],
                   help="인코딩 에러 처리 방식 (기본값: ignore)")
    p.add_argument("--no-line-number", action="store_true", help="출력 시 줄번호 생략")

    return p.parse_args()

def main():
    """
    메인 실행 함수. 전반적인 로직 흐름을 제어합니다.
    1. 설정 로드
    2. XML 파싱 (경로 토큰 수집)
    3. 배포 경로 및 대상 파일 계산
    4. 배포 명령 실행 (run-deploy 옵션 시)
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
    effective_o_list = compute_effective_O_values(config, args.config_path, rel_paths)

    # 3) -F 기준 폴더와 상대 경로를 결합하여 실제 배포할 파일(.xfdl, .xjs) 리스트 생성
    file_paths = collect_files_for_FILE_from_F(config, args.config_path, rel_paths)

    # 4) 배포 실행 (옵션 여부와 상관없이 실행하는 기존 로직 유지)
    # --run-deploy 플래그는 argparse에 있지만, 기존 로직상 호출을 막지 않았음 (필요 시 if args.run_deploy: 추가 가능)
    run_nexacro_deploy_repeat(config, args.config_path, effective_o_list, file_paths)

    sys.exit(exit_code)

if __name__ == "__main__":
    main()
