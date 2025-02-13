from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from youtube_transcript_api import YouTubeTranscriptApi
import re
from fastapi.middleware.cors import CORSMiddleware

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

def get_youtube_transcript(video_id: str) -> str:
    """자막을 추출하고 연속된 텍스트로 포맷"""
    transcript = None
    
    # 한국어 자막 시도
    try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=['ko'])
    except Exception as ko_error:
        print(f"한국어 자막 추출 실패: {str(ko_error)}")
        
        # 영어 자막 시도
        try:
            transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=['en'])
        except Exception as en_error:
            print(f"영어 자막 추출 실패: {str(en_error)}")
            
            # 모든 언어 자막 시도
            try:
                transcript = YouTubeTranscriptApi.get_transcript(video_id)
            except Exception as final_error:
                print(f"모든 자막 추출 실패: {str(final_error)}")
                raise final_error
    
    if not transcript:
        raise Exception("자막을 찾을 수 없습니다.")
        
    # 모든 자막 텍스트를 하나의 문자열로 합치기
    full_text = ' '.join(entry['text'] for entry in transcript)
    full_text = re.sub(r'\s+', ' ', full_text)
    return full_text.strip()

class TranscriptResponse(BaseModel):
    video_id: str
    transcript: str

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
        transcript_text = get_youtube_transcript(video_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"자막을 가져오는 중 오류 발생: {str(e)}")
    
    return TranscriptResponse(video_id=video_id, transcript=transcript_text)

@app.get("/api/v1/youtube/transcript", response_model=TranscriptResponse)
async def gpt_transcript(videoId: str = Query(..., description="YouTube 비디오 ID")):
    if not videoId:
        raise HTTPException(status_code=400, detail="videoId가 필요합니다.")
    
    try:
        print(f"Received videoId: {videoId}")
        transcript_text = get_youtube_transcript(videoId)
        print(f"Got transcript: {transcript_text[:100]}...")
        return TranscriptResponse(video_id=videoId, transcript=transcript_text)
    except Exception as e:
        print(f"Error occurred: {str(e)}")
        error_message = str(e)
        if "Subtitles are disabled" in error_message:
            error_message = "이 동영상은 자막이 비활성화되어 있습니다."
        raise HTTPException(status_code=500, detail=error_message)

# Vercel은 파일 내에서 "app"이라는 변수를 엔트리 포인트로 인식합니다.
