# 직진형 적

## 생성과 조절

- 적: `/Game/Enemies/BP_EnemyStraightRunner`
- 단일 생성기: `/Game/Enemies/BP_EnemyRunnerSpawner`
- 스폰 포인트: `/Game/Enemies/BP_EnemySpawnPoint`
- 생성기를 레벨에 배치하면 BeginPlay 후 0.1초에 해당 위치에서 적 한 마리를 생성한다. 캡슐 중심 높이로 배치하고 벽/바닥에 묻히지 않게 한다. 빈 공간을 확보할 수 없으면 생성하지 않는다.
- 스폰 포인트를 레벨에 배치하면 해당 위치에서 `BP_EnemyStraightRunner` 한 마리를 생성한다. Details의 `SpawnSpeed`로 생성 적의 속도를, `SpawnDelay`로 BeginPlay 후 생성까지의 지연(초)을 조절한다. 포인트의 화살표가 배치 위치와 방향을 보여준다.
- 생성기의 Details에서 `MoveSpeed`를 변경한다. 기본값 400 cm/s. 0 이하이면 정지한다.
- 적을 직접 배치하거나 Spawn Actor from Class로 생성해도 된다. 적의 `MoveSpeed` 역시 인스턴스에서 조절 가능하고 실행 중 변경도 반영된다.
- 이동은 가속/제동이 있는 CharacterMovement 기반이다. MoveSpeed는 최대 보행 속도이며 벽을 통과하거나 장애물을 우회하지 않는다.

## 방향 규칙

BeginPlay에서 Player 0의 위치를 한 번 읽어 `(플레이어 위치 - 스폰 위치)`의 XY 방향을 정규화해 `TravelDirection`에 저장한다. 이후 플레이어 위치를 다시 읽거나 추적하지 않는다. 메시 방향도 처음에만 진행 방향으로 설정한다. 플레이어가 없는 상태에서 생성되면 안전하게 이동을 비활성화한다. 따라서 플레이어 생성 이후에 스폰해야 한다.

연속 이동 입력에만 Event Tick을 사용한다. Tick에서 방향 재계산은 하지 않으며 사망 시 Tick을 끈다. AIController와 NavMesh는 필요 없다.

## 탄 충돌과 사망

Unreal의 Object Channel `Bullet`을 `ECC_GameTraceChannel1`에 추가했다. Project Settings에 이름이 아직 표시되지 않으면 에디터를 재시작한다.

탄의 실제 충돌 컴포넌트를 다음과 같이 설정한다.

- Object Type: `Bullet`
- Collision Enabled: `Query Only` 또는 `Query and Physics`
- Pawn 응답: `Overlap`
- Generate Overlap Events: 켬

적 캡슐은 Bullet을 Overlap한다. Overlap 또는 Hit에서 Bullet 타입을 확인해 Die 함수를 호출하며, Dead 플래그로 중복 사망을 막는다. 이동 및 충돌을 끄고 `DeathAnimation`을 한 번 재생한 뒤 애니메이션 길이 + 0.1초 후 제거한다. 탄의 제거/관통 정책은 적이 변경하지 않는다.

현재 프로젝트에 실제 탄 Blueprint는 없어 탄 제작 자체는 추가하지 않았다. 테스트에서는 임시 Bullet 충돌 오브젝트를 사용했다.

## 다른 적 타입 만들기

`BP_EnemyStraightRunner`의 Child Blueprint를 만들어 동일한 직진/사망 동작을 재사용할 수 있다. 기본 메시로 기존 Manny Simple을 사용하고, 같은 SK_Mannequin 스켈레톤의 기존 Jog/Death 애니메이션을 연결했다. `RunAnimation`, `DeathAnimation`은 Details에서 변경할 수 있다. 다른 메시를 사용한다면 애니메이션의 스켈레톤 호환성도 맞춰야 한다.

이 생성기는 이번 직진형 적 한 마리용이다. 웨이브, 공격, 무기 드롭 등 요청하지 않은 기능은 포함하지 않는다.

## 검증

UE 5.8 에디터에서 두 Blueprint를 컴파일하고 저장했다. 임시 테스트 Blueprint로 PIE 실행 후 로그에서 다음 항목의 PASS를 확인했다.

- 이동 속도 100 설정 후 실제 이동
- 플레이어 위치를 옆으로 이동해도 초기 직진 방향 유지
- 속도 0에서 정지
- 실행 중 속도를 200으로 변경하면 이동 속도 반영
- Bullet 오브젝트와 접촉하면 Dead 전환
- 사망 후 지연 제거

테스트용 Blueprint와 배치 액터는 제거했고 기존 레벨을 저장하거나 플레이어 Blueprint를 수정하지 않았다. 사망 애니메이션의 미적인 품질과 실제 무기 탄과의 통합은 플레이 테스트에서 추가 확인한다.
