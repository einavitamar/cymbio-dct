import cv2
import mediapipe as mp

def detect_and_crop_mediapipe(image_path, output_path):
    # Load the image
    image = cv2.imread(image_path)
    if image is None:
        print("Error: Could not load image.")
        return

    # Initialize MediaPipe Face Mesh
    mp_face_mesh = mp.solutions.face_mesh
    face_mesh = mp_face_mesh.FaceMesh(static_image_mode=True, refine_landmarks=True, max_num_faces=1)

    # Convert the image to RGB (MediaPipe requires RGB format)
    image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

    # Process the image to detect face landmarks
    results = face_mesh.process(image_rgb)

    if results.multi_face_landmarks:
        for face_landmarks in results.multi_face_landmarks:
            # Get landmarks for nose and mouth
            nose_landmark = face_landmarks.landmark[1]  # Nose tip (landmark index may vary)
            mouth_landmark_upper = face_landmarks.landmark[13]  # Upper lip
            mouth_landmark_lower = face_landmarks.landmark[14]  # Lower lip

            # Convert normalized coordinates to pixel values
            h, w, _ = image.shape
            nose_y = int(nose_landmark.y * h)
            mouth_y = int(mouth_landmark_lower.y * h)

            # Crop the image between the nose and the mouth
            cropped_image = image[nose_y:mouth_y, :]

            # Save the cropped image
            cv2.imwrite(output_path, cropped_image)
            print(f"Cropped image saved at: {output_path}")
            break
    else:
        print("No face landmarks detected.")

# Example usage
detect_and_crop_mediapipe("/Users/einavitamar/Downloads/face2.jpg", "output_cropped.jpg")
