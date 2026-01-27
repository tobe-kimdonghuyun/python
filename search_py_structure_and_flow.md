# search.py 구조 및 흐름 분석

이 문서는 고도화된 `search.py` 파일의 내부 코드 구조와 실행 흐름(Workflow)을 분석하여 기술합니다.

## 1. 파일 구조 (File Structure)

### 모듈 임포트

- `argparse`: 커맨드라인 인자 파싱
- `os`, `sys`, `shutil`: 파일 시스템 및 시스템 조작 (특히 `Geninfo.xml` 복사/삭제)
- `re`: 정규 표현식 (XML 파싱용)
- `json`: 설정 파일(.json) 로드
- `subprocess`: 외부 프로세스(nexacroDeployExecute) 실행
- **`core.*`**: 리팩토링된 핵심 모듈 기능 공유 (`deploy_manager`, `config_manager` 등)

### 주요 함수 목록

| 함수명                       | 역할                | 비고                                                     |
| :--------------------------- | :------------------ | :------------------------------------------------------- |
| `main()`                     | 프로그램 진입점     | 전체 흐름 및 임시 XML 생명주기 제어                      |
| `find_geninfo_file()`        | 설정 파일 탐색      | CWD 및 EXE 폴더에서 `$Geninfo$.geninfo` 검색 (core 공유) |
| `load_config_from_geninfo()` | XML 설정 파싱       | `$Geninfo$.geninfo`를 읽어 배포 설정 Dict 생성           |
| `run_project_deploy_cycle()` | 프로젝트 배포 실행  | Phase 1: 전체 프로젝트 구조 배포 (-O 전용 / -D 포함)     |
| `run_file_deploy_cycle()`    | 파일 단위 배포 실행 | Phase 2: 특정 파일 배포 및 JS 이동                       |
| `cleanup_test_files()`       | 테스트 결과물 정리  | `--test` 옵션 시 하위 작업 폴더만 안전하게 제거          |

---

## 2. 실행 흐름도 (Execution Flow)

```mermaid
flowchart TD
    START([시작]) --> INIT[변수 초기화 및 인자 파싱]
    INIT --> FIND_CFG{설정 파일 탐색}

    FIND_CFG -- .geninfo 발견 --> COPY_XML[원본 폴더에 Geninfo.xml 복사]
    COPY_XML --> LOAD_XML[설정 데이터 로드]

    FIND_CFG -- .json 사용 --> LOAD_JSON[JSON 로드]

    LOAD_XML & LOAD_JSON --> SEARCH_TOKENS[typedefinition.xml에서 상대 경로 토큰 추출]

    subgraph Cycle_1 [Cycle 1: -O 사이클]
        SEARCH_TOKENS --> PROJ_DEPLOY_O[2.1 Project Deploy to -O]
        PROJ_DEPLOY_O --> FILE_DEPLOY_O[2.2 & 2.3 File Deploy to -O + JS 이동]
    end

    subgraph Cycle_2 [Cycle 2: -D 사이클 (옵션)]
        FILE_DEPLOY_O --> CHECK_D{base_d 존재?}
        CHECK_D -- Yes --> PROJ_DEPLOY_D[2.4 Project Deploy with -D]
        PROJ_DEPLOY_D --> FILE_DEPLOY_D[2.5 & 2.6 File Deploy with -D + JS 이동]
    end

    CHECK_D -- No --> CLEANUP_CHECK
    FILE_DEPLOY_D --> CLEANUP_CHECK{--test 모드?}

    CLEANUP_CHECK -- Yes --> CLEAN_UP[하위 작업 폴더 삭제]
    CLEAN_UP & CLEANUP_CHECK -- No --> FINISH_XML[Geninfo.xml 삭제 (finally)]
    FINISH_XML --> END([종료])
```

---

## 3. 상세 로직 분석

### 3.1 권한 문제 해결을 위한 임시 파일 관리

- **`PermissionError` 방지**: `Geninfo.xml`을 현재 작업 디렉토리(CWD)가 아닌, **원본 설정 파일(`$Geninfo$.geninfo`)이 위치한 폴더**에 생성합니다. 이는 외부 도구(넥사크로 스튜디오) 실행 시 CWD에 권한이 없는 경우를 완벽하게 대응합니다.
- **안전한 삭제**: `try...finally` 블록을 사용하여 배포 중 에러가 발생하더라도 임시로 생성된 XML 파일이 반드시 제거되도록 보장합니다.

### 3.2 시퀀스 기반 배포 (2.1 ~ 2.6)

단순 반복 실행이 아닌, 넥사크로 배포 엔진의 특성에 맞춘 최적화된 시퀀스를 수행합니다.

1.  **-O 사이클**: 출력 경로(`-O`)를 기준으로 기초 구조를 만들고, 필터링된 파일들을 배포 및 이동합니다.
2.  **-D 사이클**: 배포 경로(`-D`) 옵션이 활성화된 경우, 동일한 과정을 `-D` 환경에 맞춰 한 번 더 실행하여 최종 결과물을 완성합니다.

### 3.3 지능형 설정 탐색

- `find_geninfo_file` 유틸리티를 통해 사용자가 인자를 주지 않아도 **현재 실행 중인 폴더**와 **스크립트/EXE가 있는 폴더**를 자동으로 뒤져 설정 파일을 찾아냅니다. 이는 사용자의 편의성을 극대화합니다.
