import os
import time

import schedule
import whisperx
from langchain.chains import ReduceDocumentsChain, MapReduceDocumentsChain
from langchain.chains.combine_documents.stuff import StuffDocumentsChain
from langchain.chains.llm import LLMChain
from langchain.chat_models import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain_text_splitters import CharacterTextSplitter
from langchain.schema.document import Document
from moviepy.editor import VideoFileClip
from openai import OpenAI
from pytube import YouTube

from view_youtube_list import get_youtube_list
from app.config.config import settings
from s3 import upload_s3

os.environ['PATH'] += os.pathsep + 'C:/Program Files/ffmpeg-6.1.1-full_build-shared/bin'

video_path = settings.VIDEO_FILE_PATH
audio_path = settings.AUDIO_FILE_PATH
script_path = settings.SCRIPT_FILE_PATH
clip_path = settings.CLIP_FILE_PATH
image_path = settings.IMAGE_FILE_PATH


def download_list():
    youtube_list = get_youtube_list()
    for link in youtube_list:
        download_video(link)
    print(youtube_list)


def download_video(path):
    video_url = 'https://www.youtube.com/watch?v=' + path
    yt = YouTube(video_url)

    # 쇼츠는 제외
    if yt.length <= 150 or yt.length > 2400:
        return
    print(yt)

    try:
        yt.streams.filter(progressive=True, file_extension='mp4').order_by('resolution').desc().first().download(
            video_path)
    except Exception as e:
        print(e)
        print("No video: " + video_url)


def video_to_audio():
    dir_list = os.listdir(video_path)
    for path in dir_list:
        if path.endswith('.mp4'):
            # 특수문자제거
            # save_path = re.sub(r"[^.\uAC00-\uD7A30-9a-zA-Z\s]", "", path)
            try:
                video = VideoFileClip(video_path + path)
                video.audio.write_audiofile(audio_path + path[:-4] + ".mp3")
            except Exception as e:
                print(f'Could not convert {path} to audio file \n{e}')


def delete_file(file):
    try:
        if os.path.isfile(file):
            os.remove(file)
            print(f"File '{file}' has been successfully deleted.")
        else:
            print(f"File '{file}' does not exist.")
    except Exception as e:
        print(f"An error occurred: {str(e)}")


def audio_to_text_model():
    dir_list = os.listdir(audio_path)
    for path in dir_list:
        print(path)
        device = "cuda"
        # audio_file = "./whisper/audio/육아휴직 중 해외 여행 부정 수급일까 shorts.mp3"  # audio_path + path
        audio_file = audio_path + path
        batch_size = 4  # reduce if low on GPU mem
        compute_type = "int8"  # change to "int8" if low on GPU mem (may reduce accuracy)

        # 1. Transcribe with original whisper (batched)
        model = whisperx.load_model("large-v2", device, compute_type=compute_type, language="ko",
                                    download_root="./whisper/model")

        # save model to local path (optional)
        # model_dir = "/path/"
        # model = whisperx.load_model("large-v2", device, compute_type=compute_type, download_root=model_dir)
        audio = whisperx.load_audio(audio_file)
        result = model.transcribe(audio, batch_size=batch_size)

        print(result["segments"])  # before alignment
        print(result)

        # save scripts
        f = open(script_path + path[:-4] + ".txt", "w", encoding="utf-8")
        f.write(str(result))
        f.close()

        # delete audio
        # delete_file(audio_file)


def summary_script(file):
    print("요약 문서: " + file)
    # 문서요약하기
    with open(file, "r",
              encoding="utf-8") as f:
        read_text = f.read()

    text_splitter = CharacterTextSplitter.from_tiktoken_encoder(
        chunk_size=4000, chunk_overlap=0
    )

    docs = [Document(page_content=x) for x in text_splitter.split_text(read_text)]
    split_docs = text_splitter.split_documents(docs)

    # Map 프롬프트
    map_template = """다음은 여러 개의 문서입니다.
        {docs}
        당신은 주어진 문서에서 주요 주제를 추출하는 데 도움이 되는 전문 기자입니다.
        이 문서 목록을 기반으로 주요 주제를 식별해 주세요.
        주요 주제에는 해당 타임스탬프도 같이 포함해 주세요.
        타임스탬프 형식은 (시작: 0.123, 끝: 130.643) 입니다.
        주제 하나마다 주요 정치관련 키워드도 세개 식별해주세요.
        차근차근 단계적으로 생각해주세요.
        
        아래는 예시 입니다. 
        총선 및 지방선거 등록 및 선거운동 (키워드:선거보조금, 의석수, 선거운동) (시작: 0.009, 끝: 100.811)
        
        주의:
        주제를 10개 이상 나열하지 마십시오.
        주제의 길이가 300초를 초과하지 않도록 주의하십시오.
        
        도움이 되는 답변:"""

    # + 주요 테마에 대해서 예시 추가하기.
    map_prompt = PromptTemplate.from_template(map_template)

    # Reduce 프롬프트
    reduce_template = """다음은 여러 개의 요약입니다:
        {doc_summaries}
        당신은 요약 작성에 능숙한 전문가입니다.
        번호가 매겨진 요약 목록이 주어졌습니다.
        요약 목록에서 상위 3가지 중요한 통찰을 추출한 후에, 해당 통찰의 요약을 작성하겠습니다.
        주요 테마에는 타임스탬프도 같이 포함해 주세요.
        타임스탬프 형식은 (시작: 0.123, 끝: 130.643) 입니다.
        단락 하나마다 주요 정치관련 키워드도 세개 식별해주세요.
        키워드는 제목에 포함된 단어가 들어가지 않아야합니다.
        키워드 형식은 (키워드:박영진 의원, 강북 공천, 한민수 후보) 입니다.
        차근차근 단계적으로 생각해주세요.
        
        아래는 예시입니다.
        1. 당정 갈등 및 화해 (키워드: 윤석열 대통령, 한동훈 비대위원장, 황상무 대통령 수석)
         - 호주대사 이종석의 사건으로 인한 수사가 진행 중이며, 이에 따라 출국이 불투명해지고 있다. (시작: 0.009, 끝: 146.954)
        2. 총선 공천과 비례대표 명단 발표 (키워드: 국민의 미래, 더불어민주연합, 조국 혁신당)
         - 민주당 내부에서 박용진 의원과 조수진 변호사 간의 공천을 둘러싼 정치적 갈등이 고조되고 있다. (시작: 186.937, 끝: 441.596)
        3. 강북을 중심으로 한 민주당 공천 논란 (키워드: 박영진 의원, 강북 공천, 한민수 후보)
         - 조국신당을 중심으로 한 정권심판론과 정책 대결이 치열하게 전개되고 있으며, 이는 선거 전략에 영향을 미칠 것으로 보인다. (시작: 973.268, 끝: 1049.48)
    
        주의:
        요약을 3개 이상 나열하지 마십시오.
        주제의 길이가 300초를 초과하지 않도록 주의하십시오.
        
        도움이 되는 답변:"""

    # 방법 1.
    # 요약을 먼저하고 (타임스탬프 미포함)
    # 스크립트에서 해당 주제에 관련된 부분을 찾기

    # 방법 2.
    # 문단 별로 스크립트를 요약하고 타임스탬프를 기입하기
    # 요약된 스크립트 리스트에서 중요하다고 생각하는 부분을 뽑아내기
    reduce_prompt = PromptTemplate.from_template(reduce_template)
    # print(f'reduce_prompt: {reduce_prompt}')
    llm = ChatOpenAI(temperature=0, openai_api_key=settings.OPENAI_API_KEY)

    # 1. Reduce chain
    reduce_chain = LLMChain(llm=llm, prompt=reduce_prompt)

    combine_documents_chain = StuffDocumentsChain(
        llm_chain=reduce_chain, document_variable_name="doc_summaries"
    )

    reduce_documents_chain = ReduceDocumentsChain(
        combine_documents_chain=combine_documents_chain,
        collapse_documents_chain=combine_documents_chain,
        token_max=4000,
    )

    # 2. Map chain
    map_chain = LLMChain(llm=llm, prompt=map_prompt)

    map_reduce_chain = MapReduceDocumentsChain(
        llm_chain=map_chain,
        reduce_documents_chain=reduce_documents_chain,
        document_variable_name="docs",
        return_intermediate_steps=False,
    )

    try:
        sum_result = map_reduce_chain.run(split_docs)
        print(sum_result)
        train_path = "./fine_tuning/train.jsonl"

        # data = {
        #     "prompt": ,
        #
        # }

        return sum_result

    except Exception as e:
        print(e)
        print("To Long Text: " + file)


def divide_video():
    dir_list = os.listdir(script_path)
    for path in dir_list:
        if not path.startswith("[KEYWORD]"):
            sum_result = summary_script(script_path + path[:-4] + ".txt")
            #         sum_result = """1. 당정 갈등과 정치권 분쟁 (키워드: 윤석열, 한동훈, 황상무) (시작: 12.5, 끝: 87.602)
            # 2. 국민의 미래 비례대표 후보 선정 (키워드: 김혜지, 한지아, 주기환전) (시작: 106.203, 끝: 136.049)
            # 3. 강북 공천 논란과 후보 선출 (키워드: 박영진, 한민수, 박진웅) (시작: 325.469, 끝: 422.568)"""
            sum_list = sum_result.split("\n")
            for (index, line) in enumerate(sum_list):
                # 키워드 추출
                keyword_start = line.find('키워드:') + 5
                keyword_end = line[keyword_start:].find(')') + keyword_start
                keyword_list = line[keyword_start:keyword_end].split(', ')

                # 시간 추출
                time_start = line.find('시작:')
                time_end = line.find('끝:')
                sub = line[3:keyword_start - 7]
                start_time = time_formatter(line[time_start + 4:time_end - 2])
                end_time = time_formatter(line[time_end + 3: -1])
                # print(line)
                # print(line[keyword_start:keyword_end])
                # print(sub)
                # print(start_time)
                # print(end_time)
                # print(keyword_list)
                # 영상 자르기
                # clip_video = VideoFileClip(
                # video_path + "R&D 삭감에 분노한 충청···김성완 표심에 악영향 이종훈 이상민 고전 (24318)  총선핫플  국회라이브6" + ".mp4").subclip(
                # start_time, end_time)
                # save keywords

                try:
                    f = open(script_path + "[KEYWORD]" + sub + ".txt", "w", encoding="utf-8")
                    f.write(str(keyword_list))
                    f.close()
                except Exception as e:
                    print(e)
                    print("Fail to Create KEYWORD: " + path[:-4])

                try:
                    clip_video = VideoFileClip(video_path + path[:-4] + ".mp4").subclip(start_time, end_time)
                    clip_video.write_videofile(clip_path + sub + ".mp4", codec='libx264')
                except Exception as e:
                    print(e)
                    print("Fail to Edit VIDEO: " + path[:-4] + ".mp4")


def time_formatter(only_second):
    try:
        idx = only_second.find('.')
        if idx == -1:
            raise ValueError("Invalid time format: missing '.'")
        second = only_second[:idx]
        minutes, seconds = divmod(int(second), 60)
        hours, minutes = divmod(minutes, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    except ValueError as ve:
        print(f"ValueError: {ve}")
        return None
    except Exception as e:
        print(f"An error occurred: {e}")
        return None


def get_keyword_category(keyword_list):
    client = OpenAI(api_key=settings.OPENAI_API_KEY)

    # 모델 - GPT 3.5 Turbo 선택
    model = "gpt-3.5-turbo-0125"

    pre_prompt = settings.GPT_PROMPT_KEYWORD
    # 메시지 설정
    messages = [{
        "role": "user",
        "content": pre_prompt + str(keyword_list),
    }]

    # ChatGPT API 호출
    response = client.chat.completions.create(
        model=model,
        messages=messages
    )
    openai_result = response.choices[0].message.content

    return openai_result


def get_keyword_category_list():
    dir_list = os.listdir(script_path)
    for path in dir_list:
        if path.startswith("[KEYWORD]"):
            with open(script_path + path, "r", encoding="utf-8") as file:
                file_contents = file.read()

            # 카테고리 추출
            keyword_list = eval(file_contents)

            with open(script_path + path, "a", encoding="utf-8") as file:
                file.write('\n' + get_keyword_category(file_contents) + '\n')


def delete_all_files_in_directory(directory):
    dir_list = os.listdir(directory)
    for path in dir_list:
        delete_file(os.path.join(directory, path))


def delete_all_files():
    delete_all_files_in_directory(audio_path)
    delete_all_files_in_directory(script_path)
    delete_all_files_in_directory(clip_path)
    delete_all_files_in_directory(image_path)
    delete_all_files_in_directory(video_path)


def parse_video():
    print("in youtube parsing")
    download_list()
    video_to_audio()
    audio_to_text_model()
    divide_video()
    get_keyword_category_list()
    upload_s3()
    delete_all_files()


if __name__ == '__main__':
    # download_list()
    # video_to_audio()
    # audio_to_text_model()
    # divide_video()
    # get_keyword_category_list()
    # upload_s3()
    # delete_all_files()

    # schedule.every(5).seconds.do(parse_video)
    # schedule.every().day.at("00:30").do(parse_video)  # 매일 10:30에
    # print("in main")
    # while True:
    #     schedule.run_pending()
    #     time.sleep(1)

    # download_video("https://www.youtube.com/watch?v=xrQ1vxS7bRo&ab_channel=NATV%EA%B5%AD%ED%9A%8C%EB%B0%A9%EC%86%A1")
    summary_script("./whisper/script/국민의미래 선대위원장에 인요한 선임! 한동훈과 투톱 (24325)  천정배 전 법무부장관  정치한수  국회라이브1.txt")
