from flask import Flask, Response, render_template, request
import cv2
import boto3
import numpy as np
import uuid
import os
import tempfile

app = Flask(__name__)

# AWS S3 configuration (use environment variables for security)
AWS_ACCESS_KEY = os.getenv('AKIAWOOXTTUW2PR7IXV5')
AWS_SECRET_KEY = os.getenv('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')
BUCKET_NAME = os.getenv('deva23')

# Initialize S3 client
s3_client = boto3.client(
    's3',
    aws_access_key_id=AWS_ACCESS_KEY,
    aws_secret_access_key=AWS_SECRET_KEY
)

# Initialize video capture
video_capture = cv2.VideoCapture(0)

def apply_filter(frame, filter_type):
    """Apply selected filter to the video frame."""
    if filter_type == 'grayscale':
        return cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    elif filter_type == 'invert':
        return cv2.bitwise_not(frame)  # Invert colors
    elif filter_type == 'sepia':
        sepia_filter = np.array([[0.272, 0.534, 0.131],
                                  [0.349, 0.686, 0.168],
                                  [0.393, 0.769, 0.189]])
        if frame.ndim == 3 and frame.shape[2] == 3:
            return cv2.transform(frame, sepia_filter)
    elif filter_type == 'blur':
        return cv2.GaussianBlur(frame, (15, 15), 0)
    return frame

def generate_frames(filter_type):
    """Generate video frames with applied filter."""
    while True:
        success, frame = video_capture.read()
        if not success:
            break
        frame = apply_filter(frame, filter_type)
        ret, buffer = cv2.imencode('.jpg', frame)
        frame = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

@app.route('/')
def index():
    """Render the main index page."""
    return render_template('index.html')

@app.route('/video_feed/<filter_type>')
def video_feed(filter_type):
    """Stream video feed with the specified filter."""
    return Response(generate_frames(filter_type), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/capture', methods=['POST'])
def capture():
    """Capture an image and upload it to S3."""
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
                return {'filename': filename}, 200
            except Exception as e:
                app.logger.error(f"S3 upload failed: {e}")
                return {'error': 'Failed to upload to S3'}, 500
        else:
            app.logger.error("Failed to capture image from camera")
            return {'error': 'Failed to capture image'}, 500
    except Exception as e:
        app.logger.error(f"An error occurred during capture: {e}")
        return {'error': 'An error occurred'}, 500


@app.route('/open_camera', methods=['GET'])
def open_camera():
    """Open the camera (for internal use)."""
    return {'message': 'Camera is opened'}, 200

if __name__ == '__main__':
    import eventlet
    eventlet.monkey_patch()
    app.run(debug=True, host='0.0.0.0', port=8080)

