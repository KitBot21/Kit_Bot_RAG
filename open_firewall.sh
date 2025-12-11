#!/bin/bash
# 방화벽에서 5000 포트 열기 (Ubuntu/Debian)

echo "🔥 방화벽 5000 포트 열기..."

# UFW 사용 중인지 확인
if command -v ufw &> /dev/null; then
    echo "UFW 방화벽 감지됨"
    sudo ufw allow 5000/tcp
    sudo ufw status
else
    echo "UFW 방화벽이 설치되어 있지 않습니다"
fi

# firewalld 사용 중인지 확인
if command -v firewall-cmd &> /dev/null; then
    echo "firewalld 감지됨"
    sudo firewall-cmd --permanent --add-port=5000/tcp
    sudo firewall-cmd --reload
    sudo firewall-cmd --list-ports
else
    echo "firewalld가 설치되어 있지 않습니다"
fi

echo ""
echo "✅ 완료!"
echo "📍 다른 컴퓨터에서 접속: http://$(hostname -I | awk '{print $1}'):5000"
