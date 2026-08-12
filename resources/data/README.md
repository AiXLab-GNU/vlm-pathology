# Data registry

`manifests/`에는 로컬 경로, 접근 조건, immutable hash와 사용하는 프로젝트를 기록한다.
여러 프로젝트가 쓰는 자료는 `shared/`, 단일 프로젝트 자료는 `<project_id>/` 아래에
둔다. 실제 WSI·임상자료·환자 단위 파생물은 Git에 포함하지 않는다.
