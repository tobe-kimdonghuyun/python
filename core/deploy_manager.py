import sys
import subprocess
from .config_manager import resolve_config_path_value, get_required_config_value
from .file_utils import move_js_files_from_file_dir

def build_deploy_base_command(config: dict, config_path: str) -> tuple[list[str], str]:
    """
    설정 파일에서 배포 관련 기본 명령어 인자들을 구성합니다.
    -O(출력 경로)와 -GENERATERULE은 반복 실행 시마다 달라지거나 별도 처리되므로 여기서는 제외합니다.
    
    Args:
        config (dict): 설정 데이터
        config_path (str): 설정 파일 경로
        
    Returns:
        tuple[list[str], str]: (기본 실행 명령어 리스트, GENERATERULE 값)
    """
    # 실행 파일 경로 가져오기
    exe_path = get_required_config_value(config, "nexacroDeployExecute")
    exe_path = resolve_config_path_value(config_path, exe_path)

    # 필수 옵션 값 가져오기 (-P, -B, -GENERATERULE)
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

def run_phase1_project_deploy(
    config: dict,
    config_path: str,
    effective_o_map: dict[str, str]
) -> None:
    """
    Phase 1: 프로젝트 단위 배포 실행 (파일 지정 없이)
    1단계에서는 -P, -O, -B, -GENERATERULE 및 설정된 옵션(-D, -COMPRESS, -SHRINK)들을 사용하여 전체 프로젝트 배포
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
    -P, -O, -B, -GENERATERULE, -FILE 및 설정된 옵션으로 nexacrodeploy.exe 실행
    이후 move_js_files_from_file_dir 작업 진행
    """
    base_cmd, rule_val = build_deploy_base_command(config, config_path)

    if not effective_o_map:
        print("실행할 -O 대상이 없습니다. (Services에서 상대경로 토큰을 찾지 못함)")
        sys.exit(1)

    if not file_paths_by_rel:
        print("실행할 -FILE 대상 파일이 없습니다. (xprj 파일 기준 폴더에서 .xfdl/.xjs 파일을 찾지 못함)")
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
    import shutil
    import os
    print("\n[CLEANUP] 테스트 생성 파일 삭제 중...")
    for d in created_dirs:
        if os.path.exists(d):
            try:
                shutil.rmtree(d)
                print(f"삭제됨: {d}")
            except Exception as e:
                print(f"삭제 실패: {d} - {e}")
