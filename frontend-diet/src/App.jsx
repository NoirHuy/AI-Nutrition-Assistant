import React, { useState, useRef } from 'react';
import Webcam from 'react-webcam';
import axios from 'axios';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

function App() {
  const [disease, setDisease] = useState("Béo phì (Obesity)");
  const [foodText, setFoodText] = useState("");
  const [imgSrc, setImgSrc] = useState(null);
  const [cameraOn, setCameraOn] = useState(false);
  
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [nutrition, setNutrition] = useState(null);
  
  const webcamRef = useRef(null);
  const fileInputRef = useRef(null);

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
    setLoading(true);
    setResult(null);

    let endpoint = 'http://localhost:8000/api/vision'; 
    let payload = { disease };

    try {
      if (type === 'image') {
        if (!imgSrc) throw new Error("Chưa có ảnh! Vui lòng tải ảnh lên hoặc bật Camera chụp lại.");
        const base64 = imgSrc.includes(',') ? imgSrc.split(',')[1] : imgSrc;
        payload.image_base64 = base64;
      } 
      else if (type === 'text') {
        if (!foodText) throw new Error("Vui lòng nhập tên món ăn!");
        endpoint = 'http://localhost:8000/api/chat'; 
        payload.question = foodText;
      }

      console.log("Đang truy vấn:", endpoint);
      const res = await axios.post(endpoint, payload);
      setResult(res.data.bot_response);
      setNutrition(res.data.nutrition || null);

    } catch (err) {
      console.error(err);
      setResult("❌ **Lỗi Backend:** " + (err.response?.data?.detail || err.message || "Không thể kết nối Server."));
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <main className="py-10 px-6 max-w-[1600px] mx-auto">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          
          {/* Left Column: Input & Actions */}
          <section className="lg:col-span-3 space-y-6">
            
            {/* Module 1: Hồ sơ bệnh lý */}
            <div className="bg-surface-container-lowest rounded-xl p-5 shadow-sm">
              <h3 className="font-headline font-bold text-on-surface mb-4">Hồ sơ bệnh lý</h3>
              <div className="relative">
                <select 
                  className="w-full bg-surface-container-highest border-none rounded-lg text-sm font-medium py-3 px-4 focus:ring-2 focus:ring-primary appearance-none outline-none"
                  value={disease}
                  onChange={(e) => setDisease(e.target.value)}
                >
                  <option value="Béo phì (Obesity)">Béo phì (Obesity)</option>
                  <option value="Tiểu đường Type 2">Tiểu đường Type 2</option>
                  <option value="Cao huyết áp">Cao huyết áp</option>
                  <option value="Suy thận">Suy Thận</option>
                </select>
                <span className="material-symbols-outlined absolute right-3 top-1/2 -translate-y-1/2 text-outline pointer-events-none">expand_more</span>
              </div>
            </div>

            {/* Module 2: Tra cứu */}
            <div className="bg-surface-container-lowest rounded-xl p-5 shadow-sm">
              <h3 className="font-headline font-bold text-on-surface mb-4">Tra cứu món ăn</h3>
              <div className="space-y-3">
                <div className="relative">
                  <input 
                    className="w-full bg-surface-container-highest border-none rounded-lg text-sm py-3 px-4 focus:ring-2 focus:ring-secondary outline-none" 
                    placeholder="Nhập tên món ăn..." 
                    type="text" 
                    value={foodText}
                    onChange={(e) => setFoodText(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && handleAnalyze('text')}
                  />
                </div>
                <button 
                  onClick={() => handleAnalyze('text')}
                  className="w-full flex items-center justify-center gap-2 bg-secondary text-white font-bold py-3 rounded-xl hover:opacity-90 transition-opacity active:scale-95 duration-150"
                >
                  <span className="material-symbols-outlined">search</span> Kiểm tra
                </button>
              </div>
            </div>

            {/* Module 3: Tải ảnh */}
            <div className="bg-surface-container-lowest rounded-xl p-5 shadow-sm overflow-hidden border border-outline-variant/10">
              <input type="file" ref={fileInputRef} onChange={handleUpload} hidden accept="image/*" />
              <div 
                className="relative aspect-video rounded-lg overflow-hidden mb-4 bg-surface-container-high cursor-pointer"
                onClick={() => fileInputRef.current?.click()}
              >
                {imgSrc ? (
                  <img alt="Món ăn" className="w-full h-full object-cover" src={imgSrc} />
                ) : (
                  <>
                    <img alt="Demo" className="w-full h-full object-cover opacity-50" src="https://lh3.googleusercontent.com/aida-public/AB6AXuDI9hU5J0k4qXhqHkqV-TCF_1GAiQ-PIk2e6OQRbi3JZCehcCO98VKsF_btge6xlMcmFvFT8Czf-zNELeLtHobQZgUdjq9xUu4bREODUXGCYVICQF9UTCYzF8_ro02y1owdH2IGkdveL1S7NUbv3e4guK3cGbfTprB5E5-jffmIsW5qq7B5lWOi9ZaEI85ZZaWJwydTWanyCvL8hKH_lpfSUIr-vYYhbQz3y1agivsNCZrXpe4q-fW6sX3M-U8oJDune1KEQ8Jg344" />
                    <div className="absolute inset-0 flex items-center justify-center font-bold text-white drop-shadow-md">Nhấn để Tải ảnh mới</div>
                  </>
                )}
                <div className="absolute inset-0 bg-black/10 pointer-events-none"></div>
              </div>
              <button 
                onClick={() => handleAnalyze('image')}
                className="w-full bg-primary text-white font-bold py-4 rounded-xl hover:shadow-lg transition-all active:scale-95 text-sm"
              >
                PHÂN TÍCH ẢNH NÀY
              </button>
            </div>

            {/* Module 4: Camera */}
            <div className="bg-surface-container-lowest rounded-xl p-5 shadow-sm">
              <div className="aspect-square rounded-xl bg-surface-container-highest flex flex-col items-center justify-center text-on-surface-variant mb-4 border-2 border-dashed border-outline-variant overflow-hidden">
                {cameraOn ? (
                    <Webcam 
                      ref={webcamRef} 
                      screenshotFormat="image/jpeg" 
                      className="w-full h-full object-cover" 
                      videoConstraints={{facingMode: "environment"}} 
                    />
                  ) : (
                    <>
                      <span className="material-symbols-outlined text-4xl mb-2 text-outline">videocam_off</span>
                      <span className="text-xs font-medium">Camera đang tắt</span>
                    </>
                  )}
              </div>
              <div className="flex gap-2">
                {!cameraOn ? (
                  <button 
                    onClick={() => setCameraOn(true)}
                    className="w-full flex items-center justify-center gap-2 bg-primary-container text-white font-bold py-3 rounded-xl hover:opacity-90"
                  >
                    <span className="material-symbols-outlined">videocam</span> Bật Camera
                  </button>
                ) : (
                  <>
                    <button className="flex-1 bg-error text-white font-bold py-3 rounded-xl" onClick={() => setCameraOn(false)}>Tắt</button>
                    <button className="flex-[2] bg-success text-white font-bold py-3 rounded-xl ml-2" style={{backgroundColor: '#006b5c'}} onClick={handleCapture}>Chụp & Gán</button>
                  </>
                )}
              </div>
            </div>
            
          </section>

          {/* DYNAMIC RESULT AREA (9 columns) */}
          <section className="lg:col-span-9 space-y-6">
            {loading ? (
              <div className="glass-panel text-center rounded-xl p-10 shadow-sm flex flex-col items-center justify-center min-h-[500px]">
                <div className="animate-spin rounded-full h-20 w-20 border-t-8 border-primary border-8 border-primary/20 mb-6"></div>
                <h3 className="text-2xl font-headline font-bold text-primary">AI Đang phân tích Graph Neo4j...</h3>
                <p className="text-on-surface-variant mt-2 font-medium">Xin chờ trong giây lát</p>
              </div>
            ) : result ? (
              <div className="grid grid-cols-1 lg:grid-cols-9 gap-6">
                <div className="lg:col-span-9 space-y-6">
                  <div className="glass-panel rounded-xl p-8 shadow-sm h-full">
                    <div className="flex justify-between items-center mb-8 border-l-4 border-primary pl-4">
                      <h2 className="font-headline font-extrabold text-2xl tracking-tight text-primary m-0">KẾT QUẢ DINH DƯỠNG CHI TIẾT</h2>
                      <button onClick={() => {setResult(null); setNutrition(null);}} className="text-on-surface-variant hover:text-error transition-colors p-2 rounded-full hover:bg-error/10">
                        <span className="material-symbols-outlined">close</span>
                      </button>
                    </div>
                    
                    {nutrition && nutrition.name && (
                    <div className="bg-white p-6 rounded-lg border border-outline-variant/20 mb-8 shadow-inner">
                      <div className="border-b-4 border-on-surface pb-1 mb-4">
                        <h4 className="font-headline font-black text-xl">Thành phần dinh dưỡng</h4>
                        <p className="text-xs font-bold text-primary">Phát hiện từ Neo4j: {nutrition.name}</p>
                      </div>
                      
                      <div className="space-y-4">
                        <div className="flex flex-col gap-1">
                          <div className="flex justify-between items-end">
                            <span className="font-bold text-lg">Năng lượng</span>
                            <span className="font-black text-lg">{nutrition.calories !== "N/A" ? nutrition.calories : 0} kcal</span>
                          </div>
                          <div className="w-full h-2 bg-surface-container-high rounded-full overflow-hidden">
                            <div className="h-full bg-secondary rounded-full" style={{width: `${Math.min(((nutrition.calories !== "N/A" ? nutrition.calories : 0) || 0) / 2000 * 100, 100)}%`}}></div>
                          </div>
                        </div>

                        <div className="flex flex-col gap-1">
                          <div className="flex justify-between items-end">
                            <span className="font-bold">Chất đạm (Protein)</span>
                            <span className="font-bold">{nutrition.protein !== "N/A" ? nutrition.protein : 0}g</span>
                          </div>
                          <div className="w-full h-2 bg-surface-container-high rounded-full overflow-hidden">
                            <div className="h-full bg-primary rounded-full" style={{width: `${Math.min(((nutrition.protein !== "N/A" ? nutrition.protein : 0) || 0) / 50 * 100, 100)}%`}}></div>
                          </div>
                        </div>

                        <div className="pt-2 border-t border-outline-variant/20">
                          <div className="flex flex-col gap-1">
                            <div className="flex justify-between items-end">
                              <span className="font-bold">Tổng chất béo</span>
                              <span className="font-bold">{nutrition.fat !== "N/A" ? nutrition.fat : 0}g</span>
                            </div>
                            <div className="w-full h-2 bg-surface-container-high rounded-full overflow-hidden">
                              <div className="h-full bg-error rounded-full" style={{width: `${Math.min(((nutrition.fat !== "N/A" ? nutrition.fat : 0) || 0) / 70 * 100, 100)}%`}}></div>
                            </div>
                          </div>
                        </div>

                        <div className="flex flex-col gap-1 pt-2 border-t border-outline-variant/20">
                          <div className="flex justify-between items-end">
                            <span className="font-bold">Tinh bột (Carbs)</span>
                            <span className="font-bold">{nutrition.carbs !== "N/A" ? nutrition.carbs : 0}g</span>
                          </div>
                          <div className="w-full h-2 bg-surface-container-high rounded-full overflow-hidden">
                            <div className="h-full bg-outline-variant rounded-full" style={{width: `${Math.min(((nutrition.carbs !== "N/A" ? nutrition.carbs : 0) || 0) / 300 * 100, 100)}%`}}></div>
                          </div>
                        </div>

                        {/* Vi chất dinh dưỡng bổ sung */}
                        <div className="grid grid-cols-2 gap-x-6 gap-y-3 pt-4 border-t border-outline-variant/20">
                          <div className="flex justify-between text-sm"><span className="font-medium text-on-surface-variant">Chất xơ</span><span className="font-bold">{nutrition.fiber !== "N/A" ? nutrition.fiber : 0}g</span></div>
                          <div className="flex justify-between text-sm"><span className="font-medium text-on-surface-variant">Cholesterol</span><span className="font-bold">{nutrition.cholesterol !== "N/A" ? nutrition.cholesterol : 0}mg</span></div>
                          <div className="flex justify-between text-sm"><span className="font-medium text-on-surface-variant">Canxi</span><span className="font-bold">{nutrition.calcium !== "N/A" ? nutrition.calcium : 0}mg</span></div>
                          <div className="flex justify-between text-sm"><span className="font-medium text-on-surface-variant">Sắt</span><span className="font-bold">{nutrition.iron !== "N/A" ? nutrition.iron : 0}mg</span></div>
                          <div className="flex justify-between text-sm"><span className="font-medium text-on-surface-variant">Phốt pho</span><span className="font-bold">{nutrition.phosphorus !== "N/A" ? nutrition.phosphorus : 0}mg</span></div>
                          <div className="flex justify-between text-sm"><span className="font-medium text-on-surface-variant">Kali</span><span className="font-bold">{nutrition.potassium !== "N/A" ? nutrition.potassium : 0}mg</span></div>
                          <div className="flex justify-between text-sm"><span className="font-medium text-on-surface-variant">Natri</span><span className="font-bold">{nutrition.sodium !== "N/A" ? nutrition.sodium : 0}mg</span></div>
                          <div className="flex justify-between text-sm"><span className="font-medium text-on-surface-variant">Vitamin A</span><span className="font-bold">{nutrition.vitamin_a !== "N/A" ? nutrition.vitamin_a : 0}IU</span></div>
                          <div className="flex justify-between text-sm"><span className="font-medium text-on-surface-variant">Vitamin B1</span><span className="font-bold">{nutrition.vitamin_b1 !== "N/A" ? nutrition.vitamin_b1 : 0}mg</span></div>
                          <div className="flex justify-between text-sm"><span className="font-medium text-on-surface-variant">Vitamin C</span><span className="font-bold">{nutrition.vitamin_c !== "N/A" ? nutrition.vitamin_c : 0}mg</span></div>
                          <div className="flex justify-between text-sm col-span-2"><span className="font-medium text-on-surface-variant">Beta Carotene</span><span className="font-bold">{nutrition.beta_carotene !== "N/A" ? nutrition.beta_carotene : 0}mcg</span></div>
                        </div>

                      </div>
                    </div>
                    )}

                    <div className="bg-primary-fixed p-6 rounded-xl border border-primary/10 mb-8">
                      <div className="flex items-center gap-3 mb-3 text-on-primary-fixed-variant">
                        <span className="material-symbols-outlined" style={{fontVariationSettings: "'FILL' 1"}}>psychology</span>
                        <h4 className="font-headline font-bold">Phân tích y khoa & Lời khuyên AI</h4>
                      </div>
                      <div className="markdown-body">
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>{result}</ReactMarkdown>
                      </div>
                    </div>

                  </div>
                </div>
              </div>
            ) : (
              <div className="glass-panel text-center rounded-xl p-10 shadow-sm flex flex-col items-center justify-center min-h-[400px]">
                <span className="material-symbols-outlined text-6xl text-outline-variant mb-4">settings_system_daydream</span>
                <h3 className="text-xl font-headline font-bold text-on-surface-variant">Sẵn sàng phân tích dinh dưỡng</h3>
                <p className="text-outline mt-2 text-sm max-w-sm">Hãy chọn Hồ sơ bệnh và gõ tên món ăn hoặc gửi ảnh để hệ thống AI truy xuất thông tin từ đồ thị tri thức Neo4j.</p>
              </div>
            )}
          </section>

        </div>
      </main>

    </>
  );
}

export default App;