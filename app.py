#!/usr/bin/env python3
"""
RAG 챗봇 웹 데모 서버 (Flask)

실행 방법:
    python3 app.py
    
브라우저에서 접속:
    http://localhost:5000
"""

from flask import Flask, render_template, request, jsonify, session
from flask_cors import CORS
import sys
from pathlib import Path
import uuid
from datetime import datetime

# 프로젝트 루트 경로 추가
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from rag_demo import RAGSystem

app = Flask(__name__)
app.secret_key = 'kit-bot-rag-secret-key-2025'
CORS(app)

# RAG 시스템 초기화 (서버 시작 시 1회)
print("🚀 RAG 시스템 초기화 중...")
rag_system = RAGSystem(
    collection_name='kit_corpus_bge_all',
    retriever_model='BAAI/bge-m3',
    llm_provider='openai',
    llm_model='gpt-4o-mini'
)
print("✅ RAG 시스템 준비 완료!\n")

# 대화 이력 저장 (메모리)
conversations = {}

@app.route('/')
def index():
    """메인 페이지"""
    return render_template('index.html')

@app.route('/api/chat', methods=['POST'])
def chat():
    """채팅 API 엔드포인트"""
    try:
        data = request.json
        query = data.get('query', '').strip()
        
        if not query:
            return jsonify({
                'success': False,
                'error': '질문을 입력해주세요.'
            }), 400
        
        # 세션 ID 생성 또는 가져오기
        session_id = session.get('session_id')
        if not session_id:
            session_id = str(uuid.uuid4())
            session['session_id'] = session_id
            conversations[session_id] = []
        
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 질문: {query}")
        
        # 1. Retrieval
        contexts = rag_system.retrieve(query, top_k=3)
        
        # 2. Generation
        answer = rag_system.generate(query, contexts)
        
        # 3. 대화 이력 저장
        conversation_item = {
            'timestamp': datetime.now().isoformat(),
            'query': query,
            'answer': answer,
            'contexts': [
                {
                    'title': ctx.get('title', 'Unknown'),
                    'text': ctx.get('text', '')[:200] + '...',
                    'similarity': round(ctx.get('score', 0), 3)  # score를 similarity로 변환
                }
                for ctx in contexts
            ]
        }
        
        if session_id in conversations:
            conversations[session_id].append(conversation_item)
        
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 응답 완료\n")
        
        return jsonify({
            'success': True,
            'answer': answer,
            'contexts': conversation_item['contexts'],
            'session_id': session_id
        })
        
    except Exception as e:
        print(f"❌ 오류: {e}")
        return jsonify({
            'success': False,
            'error': f'오류가 발생했습니다: {str(e)}'
        }), 500

@app.route('/api/history', methods=['GET'])
def get_history():
    """대화 이력 조회"""
    session_id = session.get('session_id')
    
    if not session_id or session_id not in conversations:
        return jsonify({
            'success': True,
            'history': []
        })
    
    return jsonify({
        'success': True,
        'history': conversations[session_id]
    })

@app.route('/api/clear', methods=['POST'])
def clear_history():
    """대화 이력 삭제"""
    session_id = session.get('session_id')
    
    if session_id and session_id in conversations:
        conversations[session_id] = []
    
    return jsonify({
        'success': True,
        'message': '대화 이력이 삭제되었습니다.'
    })

@app.route('/api/health', methods=['GET'])
def health_check():
    """서버 상태 확인"""
    return jsonify({
        'success': True,
        'status': 'healthy',
        'model': 'BAAI/bge-m3',
        'llm': 'gpt-4o-mini'
    })

if __name__ == '__main__':
    print("\n" + "=" * 80)
    print("🤖 KIT Bot RAG 챗봇 서버")
    print("=" * 80)
    print("\n📍 접속 주소: http://localhost:5000")
    print("📍 API 엔드포인트:")
    print("   - POST /api/chat : 채팅")
    print("   - GET  /api/history : 대화 이력")
    print("   - POST /api/clear : 이력 삭제")
    print("   - GET  /api/health : 상태 확인")
    print("\n⏹️  종료: Ctrl+C")
    print("=" * 80 + "\n")
    
    app.run(host='0.0.0.0', port=5000, debug=True)
