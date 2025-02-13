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

def get_youtube_transcript(video_id: str) -> list:
    """자막을 추출하고 타임스탬프와 함께 반환"""
    transcript = None
    errors = []
    
    print(f"Starting transcript extraction for video ID: {video_id}")
    
    try:
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        
        # 한국어 자막 시도
        try:
            transcript = transcript_list.find_transcript(['ko']).fetch()
            print("한국어 자막 추출 성공")
        except:
            try:
                transcript = transcript_list.find_transcript(['en']).fetch()
                print("영어 자막 추출 성공")
            except:
                try:
                    transcript = transcript_list.find_generated_transcript(['ko', 'en']).fetch()
                    print("자동 생성 자막 추출 성공")
                except Exception as e:
                    errors.append(str(e))
                    raise Exception("사용 가능한 자막을 찾을 수 없습니다.")
    
    except Exception as e:
        print(f"Error: {str(e)}")
        raise e

    if not transcript:
        raise Exception("자막을 찾을 수 없습니다.")
    
    # transcript는 이미 필요한 형식 (list of dicts with 'text', 'start', 'duration')
    return transcript

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

# Vercel은 파일 내에서 "app"이라는 변수를 엔트리 포인트로 인식합니다.
