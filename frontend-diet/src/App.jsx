import React, { useState, useEffect, useRef } from 'react';
import Webcam from 'react-webcam';
import axios from 'axios';
import { 
  Camera, Upload, Search, HeartPulse, Activity, 
  CheckCircle, RefreshCw, X, ChevronRight, Image as ImageIcon
} from 'lucide-react';

// 👇 Thư viện xử lý văn bản AI đẹp (Bảng biểu, chữ đậm...)
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

import './App.css';

// Lấy AnimeJS từ window (do đã nạp ở index.html)
const anime = window.anime;

function App() {
  // --- STATE ---
  const [disease, setDisease] = useState("Tiểu đường");
  const [foodText, setFoodText] = useState("");
  const [imgSrc, setImgSrc] = useState(null);
  const [cameraOn, setCameraOn] = useState(false);
  
  // State quản lý Modal & Kết quả
  const [showModal, setShowModal] = useState(false);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  
  const webcamRef = useRef(null);
  const fileInputRef = useRef(null);

  // --- HIỆU ỨNG ANIMEJS ---
  
  // 1. Hiệu ứng khi mở trang (Các thẻ card bay lên)
  useEffect(() => {
    if (anime) {
      anime({
        targets: '.card',
        translateY: [30, 0],
        opacity: [0, 1],
        delay: anime.stagger(100), // Mỗi thẻ cách nhau 100ms
        easing: 'easeOutQuad'
      });
    }
  }, []);

  // 2. Hiệu ứng khi mở/đóng Modal
  useEffect(() => {
    if (showModal && anime) {
      // Làm tối nền
      anime({
        targets: '.modal-overlay',
        opacity: [0, 1],
        duration: 300,
        easing: 'linear'
      });
      // Zoom bảng kết quả
      anime({
        targets: '.modal-content',
        scale: [0.8, 1],
        opacity: [0, 1],
        delay: 100,
        easing: 'spring(1, 80, 10, 0)'
      });
    }
  }, [showModal]);

  // --- XỬ LÝ LOGIC ---

  const handleCapture = () => {
    if (webcamRef.current) {
      const imageSrc = webcamRef.current.getScreenshot();
      setImgSrc(imageSrc);
      setCameraOn(false);
    }
  };

  const handleUpload = (e) => {
    const file = e.target.files[0];
    if (file) {
      const reader = new FileReader();
      reader.onloadend = () => setImgSrc(reader.result);
      reader.readAsDataURL(file);
    }
  };

  const handleAnalyze = async (type) => {
    // 1. Mở modal loading ngay lập tức
    setShowModal(true);
    setLoading(true);
    setResult(null);

    let endpoint = 'http://localhost:8000/api/vision'; 
    let payload = { disease };

    try {
      // 2. Kiểm tra dữ liệu đầu vào
      if (type === 'image') {
        if (!imgSrc) throw new Error("Chưa có ảnh! Vui lòng chụp hoặc tải ảnh.");
        const base64 = imgSrc.includes(',') ? imgSrc.split(',')[1] : imgSrc;
        payload.image_base64 = base64;
      } 
      else if (type === 'text') {
        if (!foodText) throw new Error("Vui lòng nhập tên món ăn!");
        // Gọi tạm endpoint vision hoặc đổi sang endpoint chat nếu backend đã hỗ trợ
        // Ở đây ta giả lập dùng chung logic hoặc backend xử lý text
        endpoint = 'http://localhost:8000/api/chat'; 
        payload.question = `Tôi bị ${disease}, ăn món "${foodText}" được không? Phân tích dinh dưỡng giúp tôi.`;
      }

      // 3. Gọi API
      console.log("📡 Đang gửi đến:", endpoint);
      const res = await axios.post(endpoint, payload);
      
      // 4. Nhận kết quả
      console.log("✅ Kết quả:", res.data);
      setResult(res.data.bot_response);

    } catch (err) {
      console.error("❌ Lỗi:", err);
      setResult(err.response?.data?.detail || err.message || "Lỗi kết nối Server! Vui lòng kiểm tra Docker.");
    } finally {
      setLoading(false);
    }
  };

  const closeModal = () => {
    setShowModal(false);
    // Đợi hiệu ứng đóng xong mới clear result (optional)
    setTimeout(() => setResult(null), 300);
  };

  return (
    <div className="app-container">
      {/* HEADER */}
      <nav className="navbar">
        <div className="logo">
          <HeartPulse size={28} style={{color: '#ff7675'}}/> 
          <span>AI NUTRITION</span>
        </div>
        <div style={{fontSize: '0.9rem', color: '#666', display: 'flex', alignItems: 'center', gap: 5}}>
          <Activity size={16}/> Trợ lý sức khỏe
        </div>
      </nav>

      {/* DASHBOARD GRID */}
      <div className="dashboard">
        
        {/* CARD 1: HỒ SƠ BỆNH */}
        <div className="card full-width">
          <div className="card-title">🩺 Hồ sơ bệnh lý</div>
          <div className="input-group">
            <select className="select-field" value={disease} onChange={(e) => setDisease(e.target.value)}>
              <option value="Tiểu đường">Tiểu đường (Diabetes)</option>
              <option value="Cao huyết áp">Cao huyết áp (Hypertension)</option>
              <option value="Béo phì">Béo phì (Obesity)</option>
              <option value="Gout">Gout (Thống phong)</option>
              <option value="Suy thận">Suy thận (Kidney failure)</option>
            </select>
          </div>
        </div>

        {/* CARD 2: TRA CỨU TEXT */}
        <div className="card full-width">
          <div className="card-title"><Search size={20}/> Tra cứu theo tên món</div>
          <div className="input-group">
            <input 
              className="input-field" 
              placeholder="Nhập tên món (VD: Phở bò, Trà sữa...)" 
              value={foodText}
              onChange={(e) => setFoodText(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleAnalyze('text')}
            />
            <button className="btn btn-success" onClick={() => handleAnalyze('text')}>
              <ChevronRight size={18} /> Kiểm tra
            </button>
          </div>
        </div>

        {/* CARD 3: UPLOAD ẢNH */}
        <div className="card">
          <div className="card-title"><Upload size={20}/> Tải ảnh có sẵn</div>
          <input type="file" ref={fileInputRef} onChange={handleUpload} hidden accept="image/*" />
          
          <div className="upload-area" onClick={() => fileInputRef.current.click()}>
            {imgSrc ? (
              <img src={imgSrc} alt="Preview" className="preview-img" />
            ) : (
              <div style={{textAlign:'center', color:'#888'}}>
                <Upload size={40} style={{marginBottom:10, color: '#a29bfe'}}/>
                <div>Click để chọn ảnh</div>
                <small style={{opacity: 0.6}}>JPG, PNG, JPEG</small>
              </div>
            )}
          </div>
          
          {imgSrc && (
            <button className="btn btn-primary" style={{marginTop: 15, justifyContent: 'center'}} onClick={() => handleAnalyze('image')}>
              <Search size={18}/> PHÂN TÍCH ẢNH NÀY
            </button>
          )}
        </div>

        {/* CARD 4: CAMERA */}
        <div className="card">
          <div className="card-title"><Camera size={20}/> Chụp ảnh trực tiếp</div>
          <div className="camera-box">
            {cameraOn ? (
              <Webcam 
                ref={webcamRef} 
                screenshotFormat="image/jpeg" 
                className="video-feed" 
                videoConstraints={{facingMode: "environment"}} 
                onUserMediaError={() => alert("Không tìm thấy Camera!")}
              />
            ) : (
              <div style={{color:'#666', textAlign:'center'}}>
                <Camera size={40} style={{marginBottom:10, color: '#a29bfe'}}/>
                <div>Camera đang tắt</div>
              </div>
            )}
          </div>
          <div style={{display:'flex', gap:10, marginTop:15, justifyContent:'center'}}>
            {!cameraOn ? (
              <button className="btn btn-primary" onClick={() => setCameraOn(true)}>Bật Camera</button>
            ) : (
              <>
                <button className="btn btn-danger" onClick={() => setCameraOn(false)}>Tắt</button>
                <button className="btn btn-success" onClick={handleCapture}>Chụp ảnh</button>
              </>
            )}
          </div>
        </div>

      </div>

      {/* --- MODAL KẾT QUẢ --- */}
      {showModal && (
        <div className="modal-overlay">
          <div className="modal-content">
            
            {/* Header Modal */}
            <div style={{display:'flex', justifyContent:'space-between', alignItems:'center', borderBottom: '1px solid #eee', paddingBottom: 15, marginBottom: 15}}>
              <h2 style={{margin:0, color: 'var(--primary)', display:'flex', gap:10, alignItems:'center', fontSize: '1.3rem'}}>
                {loading ? <RefreshCw className="spin"/> : <CheckCircle />}
                {loading ? "Đang phân tích..." : "Kết quả tư vấn"}
              </h2>
              {!loading && (
                <button onClick={closeModal} style={{background:'none', border:'none', cursor:'pointer', color: '#888'}}>
                  <X size={28}/>
                </button>
              )}
            </div>

            {/* Nội dung Modal */}
            <div style={{flex: 1, overflowY: 'auto'}}>
              {loading ? (
                <div style={{textAlign:'center', padding:40, color:'#666'}}>
                  <p style={{fontSize: '1.1rem', fontWeight: 500}}>🤖 AI Maverick & GPT-OSS đang làm việc...</p>
                  <p>Đang nhận diện món ăn và tra cứu dữ liệu y khoa.</p>
                  <div className="loader" style={{marginTop: 20, justifyContent: 'center'}}>
                    <span style={{animation: 'pulse 1s infinite'}}>Thinking...</span>
                  </div>
                </div>
              ) : (
                // 👇 PHẦN HIỂN THỊ MARKDOWN ĐẸP MẮT
                <div className="markdown-body">
                  <ReactMarkdown 
                    remarkPlugins={[remarkGfm]}
                    components={{
                      // Custom hiển thị bảng để có thanh trượt trên mobile
                      table: ({node, ...props}) => (
                        <div className="table-wrapper">
                          <table {...props} />
                        </div>
                      )
                    }}
                  >
                    {result}
                  </ReactMarkdown>
                </div>
              )}
            </div>

            {/* Footer Modal */}
            {!loading && (
              <div style={{marginTop: 20, borderTop: '1px solid #eee', paddingTop: 15}}>
                <button className="btn btn-primary" style={{width:'100%', justifyContent:'center'}} onClick={closeModal}>
                  Đóng & Thử món khác
                </button>
              </div>
            )}

          </div>
        </div>
      )}

    </div>
  );
}

export default App;