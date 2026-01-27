import argparse
import os
import sys
import re
import json
import subprocess
import shutil
import xml.etree.ElementTree as ET
from core.file_utils import move_js_files_from_file_dir
from core.config_manager import resolve_config_path_value, get_required_config_value, load_config, find_geninfo_file, load_config_from_geninfo

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

    p.add_argument("config_path", nargs="?", help="config.json 경로 (생략 시 $Geninfo$.geninfo 사용)")
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

def get_base_dir_from_P(config: dict, config_path: str) -> str:
    """
    '-P' (xprj 파일) 경로를 기반으로 기준 디렉토리를 결정하는 함수.
    xprj 파일이 있는 폴더를 기준으로 삼습니다.

    Args:
        config (dict): 설정 데이터
        config_path (str): 설정 파일 경로

    Returns:
        str: 기준 디렉토리 절대 경로
    """
    p_val = get_required_config_value(config, "-P")
    p_val = resolve_config_path_value(config_path, p_val)

    return os.path.dirname(p_val)

def build_deploy_base_command(config: dict, config_path: str, include_d: bool = False) -> tuple[list[str], str]:
    """
    배포 실행에 필요한 기본 명령어와 GENERATERULE 값을 준비하는 함수.
    """
    exe_path = get_required_config_value(config, "nexacroDeployExecute")
    exe_path = resolve_config_path_value(config_path, exe_path)

    p_val = resolve_config_path_value(config_path, get_required_config_value(config, "-P"))
    b_val = resolve_config_path_value(config_path, get_required_config_value(config, "-B"))
    rule_val = resolve_config_path_value(config_path, get_required_config_value(config, "-GENERATERULE"))

    base_cmd_list = [
        exe_path,
        "-P", p_val,
        "-B", b_val,
    ]

    if include_d:
        d_val = config.get("-D")
        if d_val and isinstance(d_val, str) and d_val.strip():
            d_val = resolve_config_path_value(config_path, d_val)
            base_cmd_list.extend(["-D", d_val])

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

def collect_files_for_FILE_from_P(config: dict, config_path: str, rel_paths: list[str]) -> dict[str, list[str]]:
    """
    -P 파일 위치를 기준으로 소스 파일들을 수집합니다.
    """
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

def run_project_deploy_cycle(
    config: dict,
    config_path: str,
    target_base: str,
    include_d: bool = False
) -> None:
    """
    Phase 1: 프로젝트 단위 배포 실행 (특정 베이스 경로 타겟)
    """
    base_cmd, rule_val = build_deploy_base_command(config, config_path, include_d=include_d)

    print(f"\n[Phase 1] {'(with -D) ' if include_d else ''}Project Deploy to: {target_base}")
    cmd = base_cmd + ["-O", target_base, "-GENERATERULE", rule_val]
    
    print(f"[RUN] {' '.join(cmd)}")
    result = subprocess.run(cmd, check=False)
    if result.returncode != 0:
        print(f"Phase 1 배포 실패 ({target_base}). 종료 코드: {result.returncode}")
        sys.exit(result.returncode)

def run_file_deploy_cycle(
    config: dict,
    config_path: str,
    target_map: dict[str, str],
    file_paths_by_rel: dict[str, list[str]],
    include_d: bool = False
) -> None:
    """
    Phase 2: 파일 단위 배포 및 JS 이동 (특정 타겟 맵 기준)
    """
    base_cmd, rule_val = build_deploy_base_command(config, config_path, include_d=include_d)

    print(f"\n[Phase 2] {'(with -D) ' if include_d else ''}File Deploy")
    for rel_path, target_o in target_map.items():
        files = file_paths_by_rel.get(rel_path, [])
        if not files:
            continue
            
        for fp in files:
            cmd = base_cmd + ["-O", target_o, "-GENERATERULE", rule_val, "-FILE", fp]
            
            print(f"[RUN] {' '.join(cmd)}")
            result = subprocess.run(cmd, check=False)
            if result.returncode != 0:
                print(f"Phase 2 배포 실패 ({fp} -> {target_o}). 종료 코드: {result.returncode}")
                sys.exit(result.returncode)
            
            # 배포 후 생성된 js 파일을 올바른 위치로 이동 (Step 2.3, 2.6)
            move_js_files_from_file_dir(fp, target_o)

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
    프로그램의 진입점.
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
            # 설정 파일 탐색 순서: 1. CWD, 2. 실행파일(exe) 위치
            geninfo_name = "$Geninfo$.geninfo"
            found_path = None
            
            # (1) 현재 디렉토리
            if os.path.isfile(geninfo_name):
                found_path = os.path.abspath(geninfo_name)
            else:
                # (2) 실행 파일(혹은 스크립트) 위치
                exe_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
                candidate = os.path.join(exe_dir, geninfo_name)
                if os.path.isfile(candidate):
                    found_path = os.path.abspath(candidate)
            
            if found_path:
                # 원본 파일이 있는 폴더에 Geninfo.xml 생성
                temp_xml = os.path.join(os.path.dirname(found_path), "Geninfo.xml")
                # 1.1 발견된 파일을 Geninfo.xml로 복사
                shutil.copy2(found_path, temp_xml)
                created_temp_xml = True
                # 1.2 Geninfo.xml 정보를 읽음
                config, config_path_for_resolve = load_config_from_geninfo(temp_xml)
            else:
                print(f"기본 설정 파일({geninfo_name})을 찾을 수 없습니다. (CWD 또는 실행파일 경로)")
                sys.exit(2)

        base_dir = get_base_dir_from_P(config, config_path_for_resolve)
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

        # 5) 정리 (테스트 모드)
        if args.test:
            cleanup_targets = []
            for rp in rel_paths:
                target_o = os.path.normpath(os.path.join(base_o, rp))
                if target_o != base_o and os.path.commonpath([base_o, target_o]) == base_o:
                    cleanup_targets.append(target_o)
                if base_d:
                    target_d = os.path.normpath(os.path.join(base_d, rp))
                    if target_d != base_d and os.path.commonpath([base_d, target_d]) == base_d:
                        cleanup_targets.append(target_d)
            cleanup_test_files(list(set(cleanup_targets)))
        
        sys.exit(exit_code)

    finally:
        # 1.3 완료되면 Geninfo.xml 삭제
        if created_temp_xml and os.path.exists(temp_xml):
            try:
                os.remove(temp_xml)
                print(f"[INFO] 임시 파일 삭제됨: {temp_xml}")
            except Exception as e:
                print(f"[WARN] 임시 파일 삭제 실패: {temp_xml} - {e}")

if __name__ == "__main__":
    main()
