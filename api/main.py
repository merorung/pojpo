from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from youtube_transcript_api import YouTubeTranscriptApi
import re

app = FastAPI(
    title="YouTube Transcript API",
    description="YouTube 동영상의 자막을 추출하는 API",
    version="1.0.0"
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

def get_youtube_transcript(video_id: str) -> str:
    """자막을 추출하고 연속된 텍스트로 포맷"""
    try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=['ko'])
    except Exception as e:
        try:
            transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=['en'])
        except Exception as e:
            transcript = YouTubeTranscriptApi.get_transcript(video_id)
    
    # 모든 자막 텍스트를 하나의 문자열로 합치기
    full_text = ' '.join(entry['text'] for entry in transcript)
    full_text = re.sub(r'\s+', ' ', full_text)
    return full_text.strip()

class TranscriptResponse(BaseModel):
    video_id: str
    transcript: str

@app.get("/transcript", response_model=TranscriptResponse)
async def transcript(url: str = Query(..., description="YouTube 동영상 URL")):
    video_id = extract_video_id(url)
    if not video_id:
        raise HTTPException(status_code=400, detail="올바르지 않은 YouTube URL입니다.")
    
    try:
        transcript_text = get_youtube_transcript(video_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"자막을 가져오는 중 오류 발생: {str(e)}")
    
    return TranscriptResponse(video_id=video_id, transcript=transcript_text)

# Vercel은 파일 내에서 "app"이라는 변수를 엔트리 포인트로 인식합니다.
