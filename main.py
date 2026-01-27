import argparse
import sys
import os
import shutil
from core.config_manager import load_config, get_base_dir_from_P, resolve_config_path_value, get_required_config_value, load_config_from_geninfo, find_geninfo_file
from core.xml_parser import search_rel_paths_in_services_block
from core.file_utils import compute_effective_O_values, collect_files_for_FILE_from_P
from core.deploy_manager import run_project_deploy_cycle, run_file_deploy_cycle, cleanup_test_files

def parse_args():
    """
    커맨드 라인 인자를 파싱합니다.
    """
    p = argparse.ArgumentParser(
        description="Typedefinition.xml에서 문자열을 검색하고 배포를 수행합니다. (Refactored Version)"
    )

    p.add_argument("config_path", nargs="?", help="config.json 또는 $Geninfo$.geninfo 경로 (생략 시 $Geninfo$.geninfo 사용)")
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
    """
    args = parse_args()
    
    config = None
    config_path_for_resolve = None
    temp_xml = None
    created_temp_xml = False

    try:
        if args.config_path:
            target_config = os.path.abspath(args.config_path)
            if target_config.lower().endswith(".geninfo"):
                # 1.1 입력된 인자를 Geninfo.xml로 복사
                if os.path.isfile(target_config):
                    # 원본 파일이 있는 폴더에 Geninfo.xml 생성
                    temp_xml = os.path.join(os.path.dirname(target_config), "Geninfo.xml")
                    shutil.copy2(target_config, temp_xml)
                    created_temp_xml = True
                    # 1.2 Geninfo.xml 정보를 읽음
                    config, config_path_for_resolve = load_config_from_geninfo(temp_xml)
                else:
                    print(f"설정 파일을 찾을 수 없습니다: {target_config}")
                    sys.exit(2)
            else:
                config = load_config(target_config)
                config_path_for_resolve = target_config
        else:
            # 설정 파일 탐색 (CWD -> EXE dir)
            found_path = find_geninfo_file("$Geninfo$.geninfo")
            
            if found_path:
                # 원본 파일이 있는 폴더에 Geninfo.xml 생성
                temp_xml = os.path.join(os.path.dirname(found_path), "Geninfo.xml")
                # 1.1 발견된 파일을 Geninfo.xml로 복사
                shutil.copy2(found_path, temp_xml)
                created_temp_xml = True
                # 1.2 Geninfo.xml 정보를 읽음
                config, config_path_for_resolve = load_config_from_geninfo(temp_xml)
            else:
                print(f"기본 설정 파일($Geninfo$.geninfo)을 찾을 수 없습니다. (CWD 또는 실행파일 경로)")
                sys.exit(2)

        # typedefinition.xml 위치는 -P 설정값 기준으로 파악
        base_dir = get_base_dir_from_P(config, config_path_for_resolve)
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

        # 2) 파일 수집 (공통)
        file_paths_by_rel = collect_files_for_FILE_from_P(config, config_path_for_resolve, rel_paths)

        # 베이스 경로 확인
        base_o = resolve_config_path_value(config_path_for_resolve, get_required_config_value(config, "-O"))
        
        d_val = config.get("-D")
        base_d = None
        if d_val and isinstance(d_val, str) and d_val.strip():
            base_d = resolve_config_path_value(config_path_for_resolve, d_val)

        # --- Cycle 1: -O 사이클 (2.1 ~ 2.3) ---
        target_map_o = {os.path.normpath(rp): os.path.normpath(os.path.join(base_o, rp)) for rp in rel_paths}
        # 2.1 Project Deploy to -O
        run_project_deploy_cycle(config, config_path_for_resolve, base_o, include_d=False)
        # 2.2 & 2.3 File Deploy to -O and Move JS
        run_file_deploy_cycle(config, config_path_for_resolve, target_map_o, file_paths_by_rel, include_d=False)

        # --- Cycle 2: -D 사이클 (2.4 ~ 2.6) ---
        if base_d:
            target_map_d = {os.path.normpath(rp): os.path.normpath(os.path.join(base_d, rp)) for rp in rel_paths}
            # 2.4 Project Deploy with -D
            run_project_deploy_cycle(config, config_path_for_resolve, base_o, include_d=True)
            # 2.5 & 2.6 File Deploy with -D and Move JS
            run_file_deploy_cycle(config, config_path_for_resolve, target_map_d, file_paths_by_rel, include_d=True)

        # 5) 테스트 모드일 경우 정리
        if args.test:
            cleanup_targets = []
            for rp in rel_paths:
                # -O 하위 경로
                target_o = os.path.normpath(os.path.join(base_o, rp))
                if target_o != base_o and os.path.commonpath([base_o, target_o]) == base_o:
                    cleanup_targets.append(target_o)
                
                # -D 하위 경로
                if base_d:
                    target_d = os.path.normpath(os.path.join(base_d, rp))
                    if target_d != base_d and os.path.commonpath([base_d, target_d]) == base_d:
                        cleanup_targets.append(target_d)

            cleanup_test_files(list(set(cleanup_targets)))

        sys.exit(exit_code)

    finally:
        # 1.3 완료되면 Geninfo.xml 삭제
        if created_temp_xml and temp_xml and os.path.exists(temp_xml):
            try:
                os.remove(temp_xml)
                print(f"[INFO] 임시 파일 삭제됨: {temp_xml}")
            except Exception as e:
                print(f"[WARN] 임시 파일 삭제 실패: {temp_xml} - {e}")

if __name__ == "__main__":
    main()
