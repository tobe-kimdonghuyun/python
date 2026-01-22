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

    return ([
        exe_path,
        "-P", p_val,
        "-B", b_val,
        # "-O", <여기서 넣지 않음: 반복문에서 동적으로 추가>
        # "-GENERATERULE", <여기서 넣지 않음: 룰 값만 별도로 리턴하여 나중에 결합>
    ], rule_val)

def run_nexacro_deploy_repeat(config: dict, config_path: str, effective_o_list: list[str], file_paths: list[str]) -> None:
    """
    수집된 경로들을 기반으로 Nexacro 배포 명령을 반복 실행합니다.
    실행 정책:
      - 기본 옵션은 고정
      - -O 옵션은 effective_o_list를 순회하며 변경
      - 각 -O 마다 식별된 모든 파일(-FILE)에 대해 배포 명령 수행
    
    Args:
        config (dict): 설정 데이터
        config_path (str): 설정 파일 경로
        effective_o_list (list[str]): 배포 대상 출력 폴더 리스트
        file_paths (list[str]): 배포 대상 소스 파일 리스트
    """
    base_cmd, rule_val = build_deploy_base_command(config, config_path)

    if not effective_o_list:
        print("실행할 -O 대상이 없습니다. (Services에서 상대경로 토큰을 찾지 못함)")
        sys.exit(1)

    if not file_paths:
        print("실행할 -FILE 대상 파일이 없습니다. (-F 기준 폴더에서 .xfdl/.xjs 파일을 찾지 못함)")
        sys.exit(1)

    # 이중 반복문으로 모든 조합에 대해 실행
    for eff_o in effective_o_list:
        for fp in file_paths:
            # 명령어 조합: 기본명령어 + -O <경로> + -GENERATERULE <룰> + -FILE <파일>
            cmd = base_cmd + ["-O", eff_o, "-GENERATERULE", rule_val, "-FILE", fp]
            
            # 실행 로그 출력
            print("\n[RUN]", " ".join(f'"{c}"' if " " in c else c for c in cmd))
            
            # 프로세스 실행
            result = subprocess.run(cmd, check=False)
            if result.returncode != 0:
                print("nexacroDeployExecute 실행에 실패했습니다. 종료 코드:", result.returncode)
                sys.exit(result.returncode)
            
            # 생성된 JS 파일 이동 처리
            move_js_files_from_file_dir(fp, eff_o)
