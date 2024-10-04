from flask import Flask, render_template, request, jsonify, Response
import cv2
import boto3
import uuid
import os
import tempfile

app = Flask(__name__)

# AWS S3 Configuration
BUCKET_NAME = 'deva23'
s3_client = boto3.client(
    's3',
    aws_access_key_id='AKIAWOOXTTUW2PR7IXV5',
    aws_secret_access_key='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'
)

video_capture = cv2.VideoCapture(0)

def apply_filter(frame, filter_type):
    if filter_type == 'grayscale':
        return cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    elif filter_type == 'invert':
        return cv2.bitwise_not(frame)
    elif filter_type == 'sepia':
        kernel = cv2.transform(np.array(frame, dtype=np.float64), [[0.393, 0.769, 0.189],
                                                                    [0.349, 0.686, 0.168],
                                                                    [0.272, 0.534, 0.131]])
        return np.clip(kernel, 0, 255)
    elif filter_type == 'blur':
        return cv2.GaussianBlur(frame, (15, 15), 0)
    return frame

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/video_feed/<filter_type>')
def video_feed(filter_type):
    def generate():
        while True:
            success, frame = video_capture.read()
            if not success:
                break
            frame = apply_filter(frame, filter_type)
            _, buffer = cv2.imencode('.jpg', frame)
            frame_bytes = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
    return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/capture', methods=['POST'])
def capture():
    try:
        filter_type = request.form['filter_type']
        success, frame = video_capture.read()
        if success:
            frame = apply_filter(frame, filter_type)
            filename = f"{uuid.uuid4()}.jpg"

            with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as temp_file:
                temp_file_path = temp_file.name
                cv2.imwrite(temp_file_path, frame)

            try:
                # Upload the image to S3
                s3_client.upload_file(temp_file_path, BUCKET_NAME, filename)
                os.remove(temp_file_path)  # Clean up temporary file
                return jsonify({'filename': filename}), 200
            except Exception as e:
                app.logger.error(f"S3 upload failed: {e}")
                return jsonify({'error': 'Failed to upload to S3'}), 500
        else:
            app.logger.error("Failed to capture image from camera")
            return jsonify({'error': 'Failed to capture image'}), 500
    except Exception as e:
        app.logger.error(f"An error occurred during capture: {e}")
        return jsonify({'error': 'An error occurred'}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8080)
