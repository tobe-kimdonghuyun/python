import argparse
import os
import sys

from core.config_manager import (
    compute_effective_O_values,
    load_base_dir_from_F,
    load_config,
)
from core.deploy_manager import run_nexacro_deploy_repeat
from core.file_utils import collect_files_for_FILE_from_F
from core.xml_parser import search_rel_paths_in_services_block

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
    # 4) --run-deploy 옵션 여부와 상관없이 실행
    run_nexacro_deploy_repeat(config, args.config_path, effective_o_list, file_paths)

    sys.exit(exit_code)

if __name__ == "__main__":
    main()
