from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.formatters import TextFormatter
import re
from fastapi.middleware.cors import CORSMiddleware
import os
import sys
import platform
import pkg_resources

app = FastAPI(
    title="YouTube Transcript API",
    description="YouTube 동영상의 자막을 추출하는 API",
    version="1.0.0"
)

# CORS 미들웨어 추가
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 모든 origin 허용
    allow_credentials=True,
    allow_methods=["*"],  # 모든 HTTP 메소드 허용
    allow_headers=["*"],  # 모든 HTTP 헤더 허용
)

def extract_video_id(url: str) -> str:
    """여러 가지 YouTube URL 포맷에서 video ID 추출"""
    patterns = [
        r'v=([a-zA-Z0-9_-]{11})',
        r'youtu\.be/([a-zA-Z0-9_-]{11})',
        r'embed/([a-zA-Z0-9_-]{11})',
        r'^([a-zA-Z0-9_-]{11})$'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

def get_youtube_transcript(video_id: str) -> list:
    """자막을 추출하고 타임스탬프와 함께 반환"""
    # 환경 정보 출력
    print("\n=== 실행 환경 정보 ===")
    print(f"Python 버전: {sys.version}")
    print(f"플랫폼: {platform.platform()}")
    print(f"실행 위치: {os.getcwd()}")
    print(f"환경 변수: {dict(os.environ)}")
    print("=====================\n")

    try:
        # 트랜스크립트 목록 확인
        try:
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            print(f"사용 가능한 자막 목록: {transcript_list.manual_generated_transcripts}")
            print(f"자동 생성 자막 목록: {transcript_list.generated_transcripts}")
        except Exception as e:
            print(f"자막 목록 조회 실패: {str(e)}")

        # 기존 로직
        try:
            print("한국어 자막 시도 중...")
            transcript = YouTubeTranscriptApi.get_transcript(
                video_id, 
                languages=['ko'],
                preserve_formatting=True
            )
            return transcript
        except Exception as e:
            print(f"한국어 자막 실패: {str(e)}")
        
        try:
            print("영어 자막 시도 중...")
            transcript = YouTubeTranscriptApi.get_transcript(
                video_id, 
                languages=['en'],
                preserve_formatting=True
            )
            return transcript
        except Exception as e:
            print(f"영어 자막 실패: {str(e)}")
        
        print("언어 지정 없이 시도 중...")
        transcript = YouTubeTranscriptApi.get_transcript(
            video_id,
            preserve_formatting=True
        )
        print("✓ 자막 추출 성공")
        return transcript
                
    except Exception as e:
        error_msg = str(e)
        print(f"\n=== 자막 추출 최종 실패: {error_msg} ===\n")
        raise Exception(f"자막 추출 실패 (Vercel 환경): {error_msg}")

class TranscriptItem(BaseModel):
    text: str
    start: float
    duration: float

class TranscriptResponse(BaseModel):
    transcript: list[TranscriptItem]

@app.get("/")
async def root():
    return {
        "message": "YouTube 자막 추출 API에 오신 것을 환영합니다",
        "docs_url": "/docs"
    }

@app.get("/transcript", response_model=TranscriptResponse)
async def transcript(url: str = Query(..., description="YouTube 동영상 URL")):
    video_id = extract_video_id(url)
    if not video_id:
        raise HTTPException(status_code=400, detail="올바르지 않은 YouTube URL입니다.")
    
    try:
        transcript_list = get_youtube_transcript(video_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"자막을 가져오는 중 오류 발생: {str(e)}")
    
    # 응답 형식에 맞게 변환
    transcript_items = [
        TranscriptItem(
            text=item['text'],
            start=item['start'],
            duration=item['duration']
        ) for item in transcript_list
    ]
    
    return TranscriptResponse(transcript=transcript_items)

@app.get("/api/v1/youtube/transcript", response_model=TranscriptResponse)
async def gpt_transcript(videoId: str = Query(..., description="YouTube 비디오 ID")):
    if not videoId:
        raise HTTPException(status_code=400, detail="videoId가 필요합니다.")
    
    try:
        print(f"API 호출 받음 - videoId: {videoId}")
        print(f"YouTube API 버전: {YouTubeTranscriptApi.__version__}")
        transcript_list = get_youtube_transcript(videoId)
        
        # 응답 형식에 맞게 변환
        transcript_items = [
            TranscriptItem(
                text=item['text'],
                start=item['start'],
                duration=item['duration']
            ) for item in transcript_list
        ]
        
        return TranscriptResponse(transcript=transcript_items)
    
    except Exception as e:
        error_message = str(e)
        print(f"에러 발생: {error_message}")
        if "Subtitles are disabled" in error_message:
            error_message = "이 동영상은 자막이 비활성화되어 있습니다."
        elif "Could not find transcripts" in error_message:
            error_message = "이 동영상에서 사용 가능한 자막을 찾을 수 없습니다."
        raise HTTPException(status_code=404 if "찾을 수 없습니다" in error_message else 500, 
                          detail=error_message)

@app.get("/system-info")
async def system_info():
    """시스템 정보와 설치된 패키지 정보를 반환합니다."""
    installed_packages = [
        f"{pkg.key}=={pkg.version}"
        for pkg in pkg_resources.working_set
    ]
    
    return {
        "python_version": sys.version,
        "platform": platform.platform(),
        "installed_packages": installed_packages,
        "working_directory": os.getcwd(),
        "environment_variables": dict(os.environ)
    }

# Vercel은 파일 내에서 "app"이라는 변수를 엔트리 포인트로 인식합니다.
