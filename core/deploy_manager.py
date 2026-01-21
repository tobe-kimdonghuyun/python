import subprocess
import sys

from core.config_manager import get_required_config_value, resolve_config_path_value
from core.file_utils import move_js_files_from_file_dir


def build_deploy_base_command(config: dict, config_path: str) -> tuple[list[str], str]:
    """
    -O와 -GENERATERULE은 여기서 넣지 않는다.
    (요구사항: -O는 Services에서 찾은 상대경로와 결합한 값으로 매번 바뀜)
    """
    exe_path = get_required_config_value(config, "nexacroDeployExecute")
    exe_path = resolve_config_path_value(config_path, exe_path)

    p_val = resolve_config_path_value(config_path, get_required_config_value(config, "-P"))
    b_val = resolve_config_path_value(config_path, get_required_config_value(config, "-B"))
    rule_val = resolve_config_path_value(config_path, get_required_config_value(config, "-GENERATERULE"))

    return (
        [
            exe_path,
            "-P",
            p_val,
            "-B",
            b_val,
            # "-O", <여기서 넣지 않음>
            # "-GENERATERULE", <여기서 넣지 않음>
        ],
        rule_val,
    )


def run_nexacro_deploy_repeat(
    config: dict,
    config_path: str,
    effective_o_list: list[str],
    file_paths: list[str],
) -> None:
    """
    실행 정책(요구사항 3: 현재 실행 방식 유지):
    - 기본 옵션은 고정
    - -O는 effective_o_list의 값으로 순회(= Services 토큰 기반으로 재설정)
    - 각 -O에 대해, -FILE은 file_paths의 파일 개수만큼 반복 실행
    - 변하는 건 -O와 -FILE뿐이며, 그 외(-P -B -GENERATERULE)는 고정
    """
    base_cmd, rule_val = build_deploy_base_command(config, config_path)

    if not effective_o_list:
        print("실행할 -O 대상이 없습니다. (Services에서 상대경로 토큰을 찾지 못함)")
        sys.exit(1)

    if not file_paths:
        print("실행할 -FILE 대상 파일이 없습니다. (-F 기준 폴더에서 .xfdl/.xjs 파일을 찾지 못함)")
        sys.exit(1)

    for eff_o in effective_o_list:
        for fp in file_paths:
            cmd = base_cmd + ["-O", eff_o, "-GENERATERULE", rule_val, "-FILE", fp]
            print("\n[RUN]", " ".join(f'"{c}"' if " " in c else c for c in cmd))
            result = subprocess.run(cmd, check=False)
            if result.returncode != 0:
                print("nexacroDeployExecute 실행에 실패했습니다. 종료 코드:", result.returncode)
                sys.exit(result.returncode)
            move_js_files_from_file_dir(fp, eff_o)
