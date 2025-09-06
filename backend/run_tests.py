import os
import sys

# test.py가 있는 디렉토리를 sys.path에 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from test2 import AudioSynchronizer

# 테스트할 파일 목록
video_dir = "./video"

original_files = [
    os.path.join(video_dir, "원본.wav"),
    os.path.join(video_dir, "원본2.wav"),
    os.path.join(video_dir, "원본2_uvr.wav"),
]

reaction_files = [
    os.path.join(video_dir, "[비챤].wav"),
    os.path.join(video_dir, "[비챤]_aligned.wav"),
    os.path.join(video_dir, "[비챤]_aligned2.wav"),
    os.path.join(video_dir, "[비챤]_perfect_aligned.wav"),
    os.path.join(video_dir, "[비챤]__other.wav"),
    os.path.join(video_dir, "[비챤]_uvr.wav"),
]

results = []

print("--- 테스트 시작 ---")

for original_path in original_files:
    for reaction_path in reaction_files:
        print(f"\n테스트 중: 원본='{original_path}', 반응='{reaction_path}'")
        try:
            # AudioSynchronizer 인스턴스 생성 (원본 오디오 로드 및 초기화)
            synchronizer = AudioSynchronizer(original_path)

            # 반응 오디오 동기화 수행
            # output_path=None으로 설정하여 파일 저장은 하지 않음
            # desired_true_shift_samples와 desired_error_samples는 0으로 설정하여 순수 계산 오차만 확인
            _, calculated_error = synchronizer.synchronize(
                reaction_path,
                output_path=None,
                desired_true_shift_samples=0, # 이 테스트에서는 순수 계산 오차를 보기 위함
                desired_error_samples=0 # 이 테스트에서는 순수 계산 오차를 보기 위함
            )
            results.append({
                "original": original_path,
                "reaction": reaction_path,
                "error": calculated_error
            })
        except Exception as e:
            print(f"[오류] {original_path}와 {reaction_path} 테스트 중 오류 발생: {e}")
            results.append({
                "original": original_path,
                "reaction": reaction_path,
                "error": float('inf') # 오류 발생 시 무한대 오차로 처리
            })

print("\n--- 테스트 완료 ---")

# 오차를 기준으로 결과 정렬
sorted_results = sorted(results, key=lambda x: abs(x["error"])) # 절대값 기준으로 정렬

print("\n--- 오차 적은 순서대로 결과 --- ")
for r in sorted_results:
    print(f"원본: {r['original']}\n반응: {r['reaction']}\n오차: {r['error']:.6f} samples\n")
