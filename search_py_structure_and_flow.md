# search.py 구조 및 흐름 분석

이 문서는 `search.py` 파일의 내부 코드 구조와 실행 흐름(Workflow)을 분석하여 기술합니다.

## 1. 파일 구조 (File Structure)

### 모듈 임포트

- `argparse`: 커맨드라인 인자 파싱
- `os`, `sys`, `shutil`: 파일 시스템 및 시스템 조작
- `re`: 정규 표현식 (XML 파싱용)
- `json`: 설정 파일(.json) 로드
- `subprocess`: 외부 프로세스(nexacroDeployExecute) 실행

### 주요 함수 목록

| 함수명                                 | 역할                          | 비고                                 |
| :------------------------------------- | :---------------------------- | :----------------------------------- |
| `main()`                               | 프로그램 진입점 (Entry Point) | 전체 흐름 제어                       |
| `parse_args()`                         | CLI 인자 파싱                 | `--run-deploy` 등 옵션 처리          |
| `load_config()`                        | `config.json` 로드            | JSON -> Dict 변환                    |
| `resolve_config_path_value()`          | 경로 정규화                   | 상대 경로를 절대 경로로 변환         |
| `load_base_dir_from_F()`               | `-F` 옵션 기준 디렉토리 계산  | XML 파일 위치 탐색용                 |
| `search_rel_paths_in_services_block()` | XML 파싱 핵심 로직            | `<Services>` 내의 `../` 패턴 검색    |
| `compute_effective_O_values()`         | 배포 출력 경로(-O) 계산       | XML 토큰과 결합하여 동적 생성        |
| `collect_files_for_FILE_from_F()`      | 소스 파일 목록 수집           | 배포 대상 `.xfdl`, `.xjs` 파일 탐색  |
| `run_nexacro_deploy_repeat()`          | 배포 명령 반복 실행           | `-O` 및 `-FILE` 조합별 프로세스 실행 |
| `move_js_files_from_file_dir()`        | 결과물 이동 (.js)             | 생성된 JS 파일을 `-O` 경로로 이동    |

---

## 2. 실행 흐름도 (Execution Flow)

```mermaid
flowchart TD
    START([시작 (main)]) --> PARSE_ARGS[인자 파싱 (parse_args)]
    PARSE_ARGS --> LOAD_CONFIG[설정 로드 (load_config)]

    LOAD_CONFIG --> CALC_BASE[기준 경로 계산 (load_base_dir_from_F)]
    CALC_BASE --> LOAD_XML[typedefinition.xml 찾기]

    LOAD_XML -- 파일 없음 --> ERROR([에러 종료])
    LOAD_XML -- 파일 있음 --> PARSE_XML[XML 파싱 (search_rel_paths_in_services_block)]

    PARSE_XML --> CHECK_CONTAINS{--contains-only?}
    CHECK_CONTAINS -- Yes --> EXIT_MSG[결과 출력 후 종료]

    CHECK_CONTAINS -- No --> CALC_O[배포 경로 계산 (compute_effective_O_values)]
    CALC_O --> CALC_FILES[소스 파일 수집 (collect_files_for_FILE_from_F)]

    CALC_FILES --> RUN_LOOP_O{출력 경로(-O) 리스트 순회}

    RUN_LOOP_O -- 요소 있음 --> RUN_LOOP_F{소스 파일(-FILE) 리스트 순회}
    RUN_LOOP_O -- 끝 --> END([종료 (Success)])

    RUN_LOOP_F -- 요소 있음 --> BUILD_CMD[명령어 구성 (build_deploy_base_command)]
    BUILD_CMD --> EXECUTE[프로세스 실행 (subprocess.run)]

    EXECUTE -- 성공 --> MOVE_JS[JS 파일 이동 (move_js_files_from_file_dir)]
    MOVE_JS --> RUN_LOOP_F

    EXECUTE -- 실패 --> ERROR_EXEC([에러 종료])

    RUN_LOOP_F -- 끝 --> RUN_LOOP_O
```

## 3. 상세 로직 분석

### 3.1 초기화 및 설정

1. **인자 파싱**: 사용자가 입력한 `config.json` 경로와 각종 옵션(`--run-deploy`, `--contains-only` 등)을 읽어들입니다.
2. **설정 로드**: `config.json`을 읽어 딕셔너리 형태로 메모리에 올립니다. 이때 파일이 없거나 JSON 형식이 잘못되면 즉시 종료합니다.

### 3.2 XML 파싱 (탐색 단계)

- `typedefinition.xml` 파일의 위치를 찾습니다. (`-F` 옵션 기준)
- 파일을 줄 단위로 읽으며 `<Services>` 태그 내부인지 확인합니다.
- `<Services>` 태그 내부에서 정규식 `\.\./[^\"'\s<>]+`을 사용하여 `../`로 시작하는 상대 경로 문자열을 모두 추출합니다.

### 3.3 배포 준비 (경로 계산)

- **출력 경로(-O)**: 설정 파일의 `-O` 기본 경로에, 위에서 찾은 상대 경로 토큰들을 결합하여 실제 배포될 폴더 경로들의 리스트를 만듭니다. (중복 제거됨)
- **소스 파일(-FILE)**: `-F` 기준 경로에, 위에서 찾은 상대 경로 토큰들을 결합하여 해당 위치의 실제 폴더를 찾습니다. 폴더 내의 `.xfdl`, `.xjs` 파일들을 모두 수집합니다.

### 3.4 배포 실행 (반복 단계)

- 이중 반복문 구조로 실행됩니다:
  - **Outer Loop**: 계산된 출력 경로 리스트 (`effective_o_list`)
  - **Inner Loop**: 수집된 소스 파일 리스트 (`file_paths`)
- 각 반복마다 넥사크로 배포 실행 파일(`nexacroDeployExecute`)을 호출합니다.
- 호출 후에는 `move_js_files_from_file_dir` 함수가 생성된 `.js` 파일을 식별하여 원본 위치에서 목적지 폴더(`-O` 경로)로 이동시킵니다.
