import sys
import os


class CLI:
    """
    간단한 CLI 인터페이스
    - 주제어 입력
    - 영상 길이 선택 (10분/15분/20분)
    - 생성 시작
    """

    def __init__(self):
        self.duration_options = [10, 15, 20]  # 분 단위

    def run(self):
        """CLI 실행"""
        print("=" * 60)
        print("SeniorVideoFactory - 시니어 타깃 유튜브 영상 자동 생성")
        print("=" * 60)
        print()

        # 1. 주제어 입력
        keyword = input("주제어를 입력하세요 (예: 고혈압 관리): ").strip()
        if not keyword:
            print("주제어가 입력되지 않았습니다.")
            return

        # 2. 영상 길이 선택
        print()
        print("영상 길이를 선택하세요:")
        for idx, duration in enumerate(self.duration_options, 1):
            print(f"  {idx}. {duration}분")

        duration_choice = input("선택 (1-3): ").strip()
        try:
            duration_idx = int(duration_choice) - 1
            if duration_idx < 0 or duration_idx >= len(self.duration_options):
                print("잘못된 선택입니다.")
                return
            duration_minutes = self.duration_options[duration_idx]
        except ValueError:
            print("잘못된 입력입니다.")
            return

        # 3. 생성 시작
        print()
        print(f"주제어: {keyword}")
        print(f"영상 길이: {duration_minutes}분")
        print()
        print("영상 생성을 시작합니다...")

        # TODO: main.py의 run_pipeline 호출
        # from main import run_pipeline
        # result = run_pipeline(keyword, duration_minutes)

        print("TODO: 실제 파이프라인 실행")


if __name__ == "__main__":
    cli = CLI()
    cli.run()
