# 리팩토링된 소스 (Refactored Source) 구조 및 흐름 분석

이 문서는 모듈화된(`main.py` + `core/`) 리팩토링 코드의 내부 구조와 실행 흐름을 분석하여 기술합니다.

## 1. 파일 구조 (File Structure)

리팩토링된 구조는 진입점(`main.py`)과 기능별 모듈(`core/`)로 분리되어 있습니다.

```text
Project Root/
├── main.py                 # 프로그램 진입점 (Entry Point)
└── core/                   # 핵심 기능 모듈 패키지
    ├── __init__.py
    ├── config_manager.py   # 설정 파일 로드 및 경로 처리
    ├── xml_parser.py       # XML 파싱 및 경로 추출
    ├── file_utils.py       # 파일 시스템 탐색 및 조작
    └── deploy_manager.py   # 배포 명령 생성 및 실행
```

### 모듈별 핵심 함수

| 모듈                      | 함수명                                 | 역할                                             |
| :------------------------ | :------------------------------------- | :----------------------------------------------- |
| **`main.py`**             | `main()`                               | 전체 실행 흐름 정의 및 모듈 조율 (Orchestration) |
| **`core/config_manager`** | `load_config()`                        | `config.json` 로드                               |
|                           | `load_base_dir_from_F()`               | `-F` 옵션 기준 디렉토리 계산                     |
| **`core/xml_parser`**     | `search_rel_paths_in_services_block()` | XML 파일 파싱 및 상대 경로 패턴 추출             |
| **`core/file_utils`**     | `compute_effective_O_values()`         | 배포 출력 경로(-O) 리스트 생성                   |
|                           | `collect_files_for_FILE_from_F()`      | 배포 대상 소스 파일(.xfdl, .xjs) 수집            |
| **`core/deploy_manager`** | `run_nexacro_deploy_repeat()`          | 배포 프로세스 반복 실행 및 제어                  |

---

## 2. 실행 흐름도 (Execution Flow)

```mermaid
flowchart TD
    subgraph Enter Point
        START([시작 (main)]) --> ARGS[인자 파싱 (parse_args)]
    end

    subgraph Core Modules
        ARGS -- 1. 설정 로드 --> CM_LOAD[config_manager.load_config]
        CM_LOAD --> CM_BASE[config_manager.load_base_dir_from_F]

        CM_BASE -- 2. XML 파싱 --> XML_PARSE[xml_parser.search_rel_paths_in_services_block]

        XML_PARSE --> CHECK_CONTAINS{--contains-only?}
        CHECK_CONTAINS -- Yes --> EXIT([종료])

        CHECK_CONTAINS -- No --> FU_CALC_O[file_utils.compute_effective_O_values]
        FU_CALC_O -- 3. 경로/파일 계산 --> FU_COLLECT[file_utils.collect_files_for_FILE_from_F]

        FU_COLLECT -- 4. 배포 실행 --> DM_RUN[deploy_manager.run_nexacro_deploy_repeat]
    end

    subgraph Deployment Loop
        DM_RUN --> LOOP_O{출력 경로 순회}
        LOOP_O --> LOOP_F{파일 순회}
        LOOP_F --> EXEC[Subprocess 실행]
        EXEC --> MOVE[file_utils.move_js_files_from_file_dir]
        MOVE --> LOOP_F
        LOOP_F --> LOOP_O
    end

    LOOP_O --> END([종료 (Success)])
```

## 3. 리팩토링의 이점 (Advantages)

1.  **관심사의 분리 (Separation of Concerns)**:
    - 설정 관리, XML 파싱, 파일 조작, 배포 실행 로직이 각각의 전담 모듈로 분리되었습니다.
    - 예: XML 파싱 로직을 수정해도 배포 실행 로직(`deploy_manager`)에는 영향을 주지 않습니다.

2.  **가독성 향상**:
    - `main.py`는 구체적인 구현 내용 없이 전체적인 흐름(Workflow)만 보여주게 되어, 프로그램이 어떤 순서로 동작하는지 한눈에 파악할 수 있습니다.
    - 각 모듈 파일은 크기가 작아져서(50~100줄 내외) 유지보수하기 쉽습니다.

3.  **재사용성**:
    - `load_config`나 `resolve_config_path_value` 같은 유틸리티 함수들은 다른 스크립트에서도 `from core.config_manager import ...` 형태로 쉽게 가져다 쓸 수 있습니다.
