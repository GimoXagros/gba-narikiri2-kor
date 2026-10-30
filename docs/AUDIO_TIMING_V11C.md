# v1.1c 오디오 차이의 원인과 참조 코어 수정

## 결론

기록했던 한 스테레오 프레임 차이는 테스트에 사용한 mGBA 코어의 FIFO 샘플 배치 시각 계산에서 발생했다. ROM의 음원 손상이나 샘플 누락으로 판정하지 않는다. 원인을 재현하는 원래 코어는 보존하고, 별도 참조 코어에 한 줄 수정만 적용해 비교했다. ROM에 지연 명령을 삽입하거나 녹음한 PCM을 사후 수정하지 않았다.

이는 설치된 에뮬레이터나 상류 프로젝트를 갱신했다는 뜻이 아니다. **기존 mGBA 코어에서는 v1.1c에도 같은 1프레임 차이가 남는다.** 사용자 기기 및 청취 평가는 별도 검증이다.

## 실제 사건 추적

원본 코어 SHA-256은 `0d3177c927d791fef897f735d88db3646f7932d02054af108619c6df4e1597f1`이다. 동일한 저장과 입력으로 1,368게임 프레임을 실행하면 65,536Hz PCM 1,500,002스테레오 프레임이 나온다. 관찰용 콜백을 추가해도 원래 PCM 해시는 각각 그대로 재현된다.

게임 프레임 827의 Timer 0 예정 시각은 두 ROM 모두 232,189,692사이클이었다. CPU 명령 완료 후 처리되는 실제 콜백 시각은 기준선에서 232,189,693(1사이클 늦음), v1.1b에서 232,189,696(4사이클 늦음)이었다. 이때 CPU는 텍스트 렌더러·캐시 코드를 실행 중이었다.

FIFO의 이전 값(A −11/B −5)과 다음 값(A −10/B −2)은 양쪽에서 같았다. 그러나 원래 코어는 늦게 처리된 시간을 기준으로 256사이클 단위 샘플 위치를 정했다. 기준선은 배열의 2·3번, v1.1b는 3번만 갱신했다. 다음 오디오 콜백의 예정 시각은 모두 232,189,952로 같으며, 이 배열 차이가 PCM 인덱스 906,892의 좌우 차이 −576/−192와 정확히 일치한다. 이후 FIFO 상태는 다시 같아진다.

상류 소스 [timer.c](https://github.com/mgba-emu/mgba/blob/e31759b24e7a4e3899285ff720d7b573ac328ae7/src/gba/timer.c)는 지연량 `cyclesLate`를 FIFO 함수에 전달한다. [audio.c](https://github.com/mgba-emu/mgba/blob/e31759b24e7a4e3899285ff720d7b573ac328ae7/src/gba/audio.c)의 `GBAAudioSampleFIFO`는 DMA 예약에는 이 값을 반영하지만 샘플 배열 위치 계산에는 반영하지 않는다. 예정 시각을 쓰도록 `mTimingUntil(...) + cycles - 1`로 바꾸면 해당 계산의 CPU 명령 경계 의존성이 제거된다.

## 대조 빌드와 검증 범위

동일한 e31759b 소스와 컴파일 옵션으로 수정 전·후 참조 DLL을 별도로 만들었다. 소스 차이는 `src/gba/audio.c`의 위 한 줄뿐이다. 후처리·이벤트 콜백 교체 없이 새 프로세스에서 원래 입력 경로 전체를 재생했다.

| 참조 코어 | v1.1a PCM SHA-256 | v1.1b 및 v1.1c PCM SHA-256 |
| --- | --- | --- |
| 수정 전 e31759b | `69fcc6f95c88a6371798ad2eb4c2a85aabc8f15e4c2743363504f48149b481e0` | `cc347983ff7170e542ec2fa8194136e658c39d084fee9f90d1659aa4b3f67009` |
| 예정 시각 보정 | `7ce1c9c86119e960859fa99c3be61629b921352d647bc7e21ae7e83c91094833` | `7ce1c9c86119e960859fa99c3be61629b921352d647bc7e21ae7e83c91094833` |

보정한 참조 코어에서는 세 ROM의 PCM 전체가 같다. 보정은 기준선 자체에도 적용되므로 수정 전 PCM 해시를 보존하는 작업은 아니다. 별도 VBA 코어에서도 동일 경로의 버전 간 PCM 전체가 일치한다. 저장 프로필·아이템·게임 데이터와 최종 화면도 비교했다. 진단용 이벤트 시각 보정 실험에서는 각 ROM의 보정 전후 최종 CPU·사이클·EWRAM·IWRAM도 그대로였다.

이 결과는 해당 경로의 원인 규명과 참조 코어 수정 검증이다. 모든 게임·모든 타이머 모드·실기 오디오 및 청취 품질을 인증하지 않는다. 참조 DLL은 공개 ROM 패키지에 넣지 않았다.

## 수정 재현

[최소 소스 패치](audio/mgba-e31759b-fifo-timing.patch)는 mGBA `e31759b24e7a4e3899285ff720d7b573ac328ae7`에 적용한다. 해당 소스는 Jeffrey Pfau 등 mGBA 기여자들의 MPL-2.0 코드이며 이 수정 파일도 MPL-2.0 조건을 따른다. 상류의 승인·채택을 주장하지 않는다. [원본 라이선스](https://github.com/mgba-emu/mgba/blob/e31759b24e7a4e3899285ff720d7b573ac328ae7/LICENSE)를 확인한다.

수정 전 소스를 별도로 보존한 뒤 수정용 복사본에서 실행한다.

```powershell
git apply --check mgba-e31759b-fifo-timing.patch
git apply mgba-e31759b-fifo-timing.patch
cmake -S . -B build-audio-reference -G Ninja -DBUILD_LIBRETRO=ON -DSKIP_LIBRARY=ON -DBUILD_LTO=OFF -DBUILD_QT=OFF -DBUILD_SDL=OFF -DBUILD_GL=OFF -DBUILD_GLES2=OFF -DBUILD_GLES3=OFF -DUSE_EPOXY=OFF -DUSE_ZLIB=OFF -DUSE_MINIZIP=OFF -DUSE_PNG=OFF -DUSE_FFMPEG=OFF -DUSE_LIBZIP=OFF -DUSE_SQLITE3=OFF -DUSE_LZMA=OFF -DUSE_LUA=OFF -DCMAKE_BUILD_TYPE=Release
cmake --build build-audio-reference --target mgba_libretro -j 4
```

이번 대조는 Windows w64devkit GCC 16.2.0으로 수행했다. 수정 전 소스도 같은 옵션으로 빌드해야 한다. 컴파일러·빌드 경로에 따라 DLL 해시는 달라질 수 있으므로 해당 실행에 사용한 DLL 해시와 입력·ROM·PCM 해시를 함께 기록한다. 기존 설치 폴더에 덮어쓰지 않는다.
