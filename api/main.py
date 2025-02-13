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
from youtube_transcript_api._errors import NoTranscriptFound, TranscriptsDisabled, NoTranscriptAvailable

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
    """가능한 한 단순하게 자막 추출 시도"""
    print(f"자막 추출 시작: {video_id}")
    
    try:
        # 아무 옵션 없이 바로 시도
        transcript = YouTubeTranscriptApi.get_transcript(video_id)
        return transcript
        
    except (NoTranscriptFound, TranscriptsDisabled, NoTranscriptAvailable) as e:
        # 실패하면 자동 자막 시도
        try:
            print("기본 시도 실패, 자동 자막 시도...")
            transcript = YouTubeTranscriptApi.get_transcript(
                video_id,
                languages=['ko', 'en'],
                preserve_formatting=True
            )
            return transcript
        except Exception as inner_e:
            print(f"자동 자막 시도 실패: {str(inner_e)}")
            raise Exception(f"자막을 가져올 수 없습니다: {str(inner_e)}")
            
    except Exception as e:
        print(f"자막 추출 실패: {str(e)}")
        raise Exception(f"자막 추출 중 오류 발생: {str(e)}")

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
        transcript_list = get_youtube_transcript(videoId)
        
        # 응답 변환
        transcript_items = [
            TranscriptItem(
                text=item['text'],
                start=item['start'],
                duration=item['duration']
            ) for item in transcript_list
        ]
        
        return TranscriptResponse(transcript=transcript_items)
    
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

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
