import json
import os
import sys


def load_config(config_path: str) -> dict:
    if not os.path.isfile(config_path):
        print("config.json 파일을 찾을 수 없습니다:", config_path)
        sys.exit(2)

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as exc:
        print("config.json 파싱에 실패했습니다:", exc)
        sys.exit(2)


def resolve_config_path_value(config_path: str, value: str) -> str:
    """config.json 값이 상대경로면 config.json 위치 기준으로 절대경로로 바꾼다."""
    if not isinstance(value, str) or not value.strip():
        return value
    if os.path.isabs(value):
        return os.path.normpath(value)
    return os.path.normpath(os.path.join(os.path.dirname(config_path), value))


def get_required_config_value(config: dict, key: str) -> str:
    v = config.get(key)
    if not isinstance(v, str) or not v.strip():
        print(f'config.json에 "{key}" 값이 없거나 올바르지 않습니다.')
        sys.exit(2)
    return v


def load_base_dir_from_F(config: dict, config_path: str) -> str:
    """
    -F를 기준 경로로 사용.
    -F가 파일이면 그 파일의 디렉토리로, 폴더면 폴더 그대로.
    """
    f_val = get_required_config_value(config, "-F")
    f_val = resolve_config_path_value(config_path, f_val)

    if os.path.isfile(f_val):
        return os.path.dirname(f_val)
    return f_val
