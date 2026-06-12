import streamlit as st
import cv2
import yt_dlp
import os
import tempfile
from fpdf import FPDF

# ==========================================
# 🎛️ THE CONTROL PANEL 🎛️
# ==========================================
NEW_PAGE_THRESHOLD = 5.0  
UPDATE_PAGE_THRESHOLD = 0.05 
# ==========================================

st.set_page_config(page_title="YouTube to PDF Converter", page_icon="📄", layout="centered")

st.title("📹 YouTube to PDF Converter")
st.markdown("Turn any lecture or tutorial into a clean PDF of slides. Perfect for capturing notes from intense CAD tutorials or heavy thermodynamic lecture series.")

st.info("💡 **Student Gear Recommendation:** Upgrade your engineering study setup with [this top-rated laptop stand](https://amazon.com) (Your future affiliate link goes here!).")

video_url = st.text_input("Paste YouTube Link Here:", placeholder="https://www.youtube.com/watch?v=...")

if st.button("Generate PDF", type="primary"):
    if not video_url:
        st.warning("Please enter a valid link first.")
    else:
        status_text = st.empty()
        progress_bar = st.progress(0)
        
        # Create a temporary directory for the video
        temp_dir = tempfile.mkdtemp()
        video_path = os.path.join(temp_dir, "temp_video.mp4")
        
        status_text.text("Downloading video temporarily to the server...")
        
        # Tell yt-dlp to download a small mp4 file instead of streaming
        ydl_opts = {
            'format': 'best[height<=720][ext=mp4]/best',
            'outtmpl': video_path,
            'quiet': True,
            'no_warnings': True,
            'extractor_args': {'youtube': {'player_client': ['android', 'web']}}
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info_dict = ydl.extract_info(video_url, download=True)
                video_title = info_dict.get('title', 'video_summary')
                safe_title = "".join([c for c in video_title if c.isalpha() or c.isdigit() or c in ' _-']).rstrip()
        except Exception as e:
            st.error("Error downloading video. YouTube might be blocking the server connection.")
            st.stop()

        if os.path.exists(video_path):
            status_text.text("Processing video frames...")
            
            # Read from the local downloaded file
            cap = cv2.VideoCapture(video_path)
            fps = cap.get(cv2.CAP_PROP_FPS) or 30.0 
            
            ret, frame = cap.read()
            if not ret:
                st.error("Could not read downloaded video.")
                st.stop()

            prev_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            last_stable_gray = prev_gray  
            
            has_draft = False
            pages_captured = 0
            frame_count = 0
            stable_checks = 0
            
            saved_frames = []
            current_draft_frame = None

            MAX_FRAMES_TO_CHECK = int(fps * 60 * 15) 
            
            while True:
                ret, frame = cap.read()
                if not ret or frame_count > MAX_FRAMES_TO_CHECK: 
                    break
                    
                frame_count += 1
                
                if frame_count % int(fps / 2) == 0:
                    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    motion = cv2.absdiff(gray, prev_gray).mean()
                    prev_gray = gray
                    
                    if motion > 2.0: 
                        stable_checks = 0
                        continue
                        
                    stable_checks += 1
                    
                    if stable_checks == 2:
                        diff_from_last_stable = cv2.absdiff(gray, last_stable_gray).mean()
                        
                        if not has_draft:
                            current_draft_frame = frame.copy()
                            has_draft = True
                            last_stable_gray = gray
                            
                        elif diff_from_last_stable >= NEW_PAGE_THRESHOLD:
                            frame_path = os.path.join(temp_dir, f"slide_{pages_captured}.jpg")
                            cv2.imwrite(frame_path, current_draft_frame)
                            saved_frames.append(frame_path)
                            
                            pages_captured += 1
                            status_text.text(f"Extracting slides... Found {pages_captured} unique pages.")
                            
                            current_draft_frame = frame.copy()
                            last_stable_gray = gray
                            
                        elif diff_from_last_stable >= UPDATE_PAGE_THRESHOLD:
                            current_draft_frame = frame.copy()
                            last_stable_gray = gray
                            
                        stable_checks = 0

            if has_draft and current_draft_frame is not None:
                frame_path = os.path.join(temp_dir, f"slide_{pages_captured}.jpg")
                cv2.imwrite(frame_path, current_draft_frame)
                saved_frames.append(frame_path)
                pages_captured += 1

            cap.release()
            
            # 🧹 DELETE THE VIDEO IMMEDIATELY TO SAVE SERVER SPACE
            try:
                os.remove(video_path)
            except:
                pass
            
            if pages_captured > 0:
                status_text.text("Compiling into PDF...")
                progress_bar.progress(80)
                
                pdf = FPDF(orientation='L', unit='mm', format='A4')
                for img_path in saved_frames:
                    pdf.add_page()
                    pdf.image(img_path, x=0, y=0, w=297, h=210)
                
                pdf_output_path = os.path.join(temp_dir, f"{safe_title}.pdf")
                pdf.output(pdf_output_path)
                
                status_text.text("✅ Success! Your PDF is ready.")
                progress_bar.progress(100)
                
                with open(pdf_output_path, "rb") as pdf_file:
                    st.download_button(
                        label="⬇️ Download PDF Notes",
                        data=pdf_file,
                        file_name=f"{safe_title}.pdf",
                        mime="application/pdf",
                        type="primary"
                    )
            else:
                status_text.text("No stable slides found in the video.")
                progress_bar.empty()
