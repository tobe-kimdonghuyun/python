import sys
import subprocess
from .config_manager import resolve_config_path_value, get_required_config_value
from .file_utils import move_js_files_from_file_dir

def build_deploy_base_command(config: dict, config_path: str, include_d: bool = False) -> tuple[list[str], str]:
    """
    설정 파일에서 배포 관련 기본 명령어 인자들을 구성합니다.
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
            
            # 배포 후 생성된 js 파일을 올바른 위치로 이동
            move_js_files_from_file_dir(fp, target_o)

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
