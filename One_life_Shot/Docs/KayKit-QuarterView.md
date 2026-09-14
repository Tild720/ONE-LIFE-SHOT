# KayKit 캐릭터 / 고정 쿼터뷰 작업 보고

## 프로젝트 확인
Unreal Engine 5.8.2의 기존 Third Person Blueprint 구조를 유지했다. Content에 있던 KayKit 원본 FBX 및 PNG를 확인하여 Unreal 에셋으로 임포트했다. 기존 KayKit Animation Blueprint는 없어서 생성했다. 새로운 Character 클래스나 이동 시스템은 만들지 않았다.

## 사용 에셋
아래 경로는 모두 Unreal Content Browser 경로이다.

| 용도 | 경로 |
|---|---|
| Skeletal Mesh | /Game/Characters/KayKit/Meshes/SKM_Dummy |
| Skeleton | /Game/Characters/KayKit/Meshes/SK_Dummy |
| Idle (원본 Idle_A) | /Game/Characters/KayKit/Anims/A_Dummy_Idle |
| Walk (원본 Walking_A) | /Game/Characters/KayKit/Anims/A_Dummy_Walk |
| Run (원본 Running_A, 현재 연결하지 않음) | /Game/Characters/KayKit/Anims/A_Dummy_Run |
| Animation Blueprint | /Game/Characters/KayKit/Anims/ABP_Dummy |
| Blend Space 1D | /Game/Characters/KayKit/Anims/BS_Dummy_Locomotion |
| Material | /Game/Characters/KayKit/Materials/M_Dummy |
| Texture | /Game/Characters/KayKit/Textures/T_Dummy |

텍스처 원본은 KayKit Character/prototypebits_texture.png이다. T_Dummy를 M_Dummy의 Base Color에 연결했고 Roughness는 0.8이다. Skeletal Mesh 사용 플래그를 켜고 저장 및 패키지 재로드로 유지 여부를 확인했다.

## 애니메이션과 캐릭터
수정한 기존 Character: /Game/ThirdPerson/Blueprints/BP_ThirdPersonCharacter

ABP_Dummy는 Pawn의 Velocity 평면 길이로 Speed를 계산한다. BS_Dummy_Locomotion은 Speed 0에 Idle, 80과 600에 Walk를 배치하고 가중치 보간 속도 6으로 전환한다. Run은 추후 사용할 수 있는 에셋으로만 남겼으며 Sprint는 구현하지 않았다. 캐릭터와 애니메이션은 같은 SK_Dummy를 사용한다. 원본의 뼈 이름과 부모 계층을 확인했으며 Retargeter는 필요하지 않아 만들지 않았다.

Mesh Location (0, 0, -90), Rotation (Pitch 0, Yaw -90, Roll 0), Scale (0.72, 0.72, 0.72).
기존 Capsule Half Height 90 / Radius 35, Max Walk Speed 600, CharacterMovement를 유지했다. 이후 요청에 따라 Orient Rotation to Movement를 끄고 마우스 방향 회전으로 변경했다.

## 카메라와 입력
기존 CameraBoom / FollowCamera를 사용한다. CameraBoom Length 1050, Pitch -55, Yaw -45, Roll 0. Absolute Rotation은 켜고 Use Pawn Control Rotation, Inherit Pitch/Yaw/Roll, Camera Lag 및 Rotation Lag은 껐다. FollowCamera의 Use Pawn Control Rotation도 껐다. 이 값은 Character Blueprint의 컴포넌트 Details에서 수정할 수 있다.

기존 Move 함수의 AddMovementInput 흐름을 유지하고 방향 기준만 FollowCamera의 Yaw로 변경했다. Pitch와 Roll을 제외한 평면 Forward/Right를 사용한다. 기존 Input Action 및 Mapping Context 에셋은 변경하지 않았다. Aim 함수에서 Controller Yaw/Pitch 입력 호출을 제거하여 마우스와 오른쪽 스틱이 카메라를 회전시키지 않는다. 추가 요청에 따라 캐릭터는 마우스 포인터 방향을 바라본다. 카메라는 회전하지 않는다.

## 검증 및 직접 테스트
Character와 Animation Blueprint 컴파일에 성공했다. PIE 입력 주입 검사에서 Idle/Walk 포즈 변화, 이동에 따른 Speed 변화, 캐릭터 회전과 마우스 입력에도 유지되는 카메라 각도를 확인했다. 마지막 추가 검사는 플레이 세션 종료로 중단되었으므로 해당 회차 전체 통과로 취급하지 않는다. 머티리얼은 색상 표시를 확인하고 저장 후 재로드에서도 Skeletal Mesh 사용 플래그가 유지됨을 확인했다.

1. 기존 Third Person 맵에서 Play를 누른다. 캐릭터의 색상과 발 위치를 확인한다.
2. 멈추면 Idle, WASD로 이동하면 Walk가 재생되는지 확인한다.
3. W/S/A/D가 화면 위/아래/왼쪽/오른쪽 방향으로 이동하는지 확인한다.
4. 방향을 바꾸어도 카메라 각도가 고정되고 위치만 따라오는지 확인한다.
5. 마우스를 움직이면 캐릭터만 포인터 방향을 바라보고 카메라는 회전하지 않는지 확인한다.
6. 카메라 거리나 각도 조정은 BP_ThirdPersonCharacter의 CameraBoom에서 한다.

기존 점프 동작은 유지했으며 별도의 점프 애니메이션은 이번 범위에 추가하지 않았다. 전투, 무기, 조준, 대시, Sprint, UI는 구현하지 않았다.

## MCP
공식 OpenAI 개발 문서 MCP와 Unreal Editor MCP 연결을 설정했다. 프로젝트는 ModelContextProtocol, EditorToolset, SlateInspectorToolset을 사용한다. Unreal MCP 주소는 http://127.0.0.1:8000/mcp 이며 에디터 자동 시작 설정을 추가했다.

## 생성 / 수정 목록
생성한 에셋은 위 표의 9개 전체이다. 기존 수정 에셋은 BP_ThirdPersonCharacter이다.
설정 파일: One_life_Shot.uproject, Config/DefaultEditorPerProjectUserSettings.ini.
문서: Docs/KayKit-QuarterView.md.
에디터 실행 중 발생한 Intermediate/Saved 캐시와 로그는 기능 변경 에셋에 포함하지 않는다.

## 추가 변경: 원근감 제거
FollowCamera Projection Mode를 Orthographic으로 변경했다. Ortho Width는 2100이다. 기존 카메라 각도와 추적 설정은 유지한다. 화면 범위는 FollowCamera의 Ortho Width에서 조정한다. 변경 후 Blueprint 컴파일, 저장, 설정값을 확인했다.

## 카메라 추가 조정 및 이동 점검
최종 Ortho Width 1500, SpringArm Pitch -55 / Yaw -30 / Roll 0. Near Clip Plane 100, Far Clip Plane 10000. Auto Calculate Ortho Planes 및 Update Ortho Planes는 꺼서 수동 범위를 유지한다. Blueprint 컴파일 및 저장 완료.
현재 플레이어의 IMC_Default 등록과 이동 액션에 따른 위치 변화를 확인했다. Game Only 입력 모드와 게임 뷰포트 포커스를 현재 플레이 세션에서 복구했다. 종료된 세션의 잔여 LocalPlayer 객체는 검증 대상에서 제외했다. 물리 키보드 입력은 게임 창을 클릭한 뒤 WASD로 확인한다.

## 최종 추가: 마우스 방향 회전
BP_ThirdPersonCharacter의 Event Tick에서 마우스 월드 광선과 캐릭터 높이의 수평면 교차점을 구한다. 변환과 교차가 성공할 때만 Find Look At Rotation의 Yaw를 적용한다. Pitch/Roll은 0으로 유지한다. Orient Rotation to Movement는 꺼서 이동 회전과 충돌하지 않게 했다. 기존 카메라 기준 이동과 Idle/Walk는 유지한다.
BP_ThirdPersonPlayerController는 커서를 표시하고 기존 입력 매핑 등록 뒤 Game And UI 입력 모드와 게임 화면 포커스를 설정한다. 커서 캡처 시 숨김은 끈다. 사격 및 무기는 추가하지 않았다.
최종 수정 에셋: BP_ThirdPersonCharacter, BP_ThirdPersonPlayerController, M_Dummy, ABP_Dummy(컴파일 저장). 별도 맵 편집과 Intermediate/Saved 변경은 이 커밋에서 제외한다.

## 커밋 시점 검증 한계
Blueprint 컴파일 및 저장은 통과했다. PIE에서 마우스 방향에 따른 회전과 고정 카메라를 부분 확인했지만 전체 방향 자동 검증은 아직 완료하지 못했다. D3D12 GPU 크래시와 현재 맵의 Floor2~Floor10 메시 참조 누락을 확인했다. 바닥 복구는 보류되어 있으며 이 커밋은 해당 맵 수정을 포함하지 않는다. 사용자 요청에 따라 현재 변경을 먼저 커밋한다.

## 바닥 복구 및 저부하 실행 (2026-09-14)
저장되지 않아 사라진 Floor 에셋을 실제 Assets/fbx/Floor.fbx에서 /Game/Characters/KayKit/Assets/fbx/Floor로 재생성했다. M_Dummy를 사용하고 단순 박스 충돌 1개를 생성했다. Floor2~Floor10의 기존 위치와 배율을 유지하면서 메시를 연결하고 BlockAll 충돌로 저장했다. 재시작 후 9개 참조 유지 확인.
GPU 렌더링 없는 PIE에서 Idle, WASD, Stop 검사: 모두 Walking 상태, Z 약 142.25 유지. 이동 시 Speed 증가, 정지 시 Speed 0 확인.
Tools/Start-Unreal-LowLoad.ps1은 이미 에디터가 실행 중이면 중복 실행을 차단한다. DX11, 30FPS, 낮은 Scalability, 60% Screen Percentage, BelowNormal CPU 우선순위로 실행한다. 현재 세션에서 적용값을 직접 확인했다. 기본 프로젝트 RHI는 변경하지 않는다. 이 실행 방식도 무부하나 크래시 방지를 보장하지 않는다.

## 최종 카메라 프레이밍
CameraBoom Target Offset = (X 225, Y 0, Z 225). Ortho Width 1500의 15%를 월드 X/Z 오프셋으로 적용했다. 실제 화면 픽셀의 15%와는 다르다. Near Clip Plane = -1000으로 앞쪽 바닥 잘림을 해소했다. Blueprint 컴파일 및 저장 완료.
바닥 복구 후 마우스 네 방향 회전 검증에서 최대 각도 오차 0.05도 이내, 카메라 Yaw -30 고정을 확인했다.
