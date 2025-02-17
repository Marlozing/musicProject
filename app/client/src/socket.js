import { io } from 'socket.io-client';

// 서버 URL 설정 (배포 환경과 개발 환경 구분)
export const BASE_URL = process.env.NODE_ENV === 'production'
    ? `ws://${window.location.hostname}:5000`  // 배포 환경 (현재 호스트에서 WebSocket 사용)
    : 'http://121.143.26.180:5000';  // 개발 환경 (IP 주소 사용)

// SocketIO 인스턴스 생성
export const socket = io(BASE_URL, {
    transports: ['websocket'], // WebSocket을 우선 사용
    withCredentials: true, // CORS 문제 방지
});