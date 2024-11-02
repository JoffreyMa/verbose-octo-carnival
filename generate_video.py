import os
import numpy as np
import cv2
import wave
import moviepy.editor as mpy
from moviepy.editor import VideoFileClip, TextClip, CompositeVideoClip, ColorClip, AudioFileClip, concatenate_videoclips
import logging
from pydub import AudioSegment
import json


def generate_pan_animation(image, video_writer, pan_speed=0.5, num_frames=24*10):
    """
    Generate a panning animation for an image and write it to a video.

    Parameters:
    - image: The input image (numpy array) to be panned.
    - video_writer: OpenCV VideoWriter object to write frames to.
    - pan_speed: Speed of the panning effect (default is 0.5).
    - num_frames: Total number of frames for the animation (default is 24*10).
    """
    # Get the original image dimensions
    height, width, _ = image.shape

    # Generate panning frames
    for i in range(num_frames):
        shift = int(i * pan_speed * (width / num_frames))  # Gradually move to the right
        pan_img = np.roll(image, shift, axis=1)  # Pan image horizontally
        video_writer.write(pan_img)  # Write the frame to the video


def generate_zoom_animation(img, video_writer, zoom_speed=0.001, num_frames=24*5):
    """
    Generate a zoom animation for an image and write it to a video.

    Parameters:
    - img: The original image (numpy array).
    - video_writer: OpenCV VideoWriter object to write frames to.
    - zoom_speed: The rate of zoom per frame (default is 0.001).
    - num_frames: Total number of frames in the animation (default is 24*5).
    """
    # Get the original image dimensions
    height, width, _ = img.shape

    # Generate zoom frames
    for i in range(num_frames):
        zoom_factor = 1 + i * zoom_speed  # Gradual zoom effect
        zoomed_img = cv2.resize(img, None, fx=zoom_factor, fy=zoom_factor)

        # Crop the zoomed image to the original size
        zoom_height, zoom_width, _ = zoomed_img.shape
        start_x = (zoom_width - width) // 2
        start_y = (zoom_height - height) // 2
        cropped_img = zoomed_img[start_y:start_y + height, start_x:start_x + width]

        # Write the frame to the video
        video_writer.write(cropped_img)


def generate_blur_animation(image, video_writer, kernel_size=(51, 51), sigma=10, num_frames=24*3):
    """
    Apply a Gaussian blur to an image and write it to a video for a specified number of frames.

    Parameters:
    - image: The input image (numpy array) to be blurred.
    - video_writer: OpenCV VideoWriter object to write frames to.
    - kernel_size: Size of the Gaussian kernel (default is (51, 51)).
    - sigma: Standard deviation for the Gaussian blur (default is 10).
    - num_frames: Total number of frames to write to the video (default is 24*3).
    """
    # Apply Gaussian blur using OpenCV
    blurred_image = cv2.GaussianBlur(image, kernel_size, sigma)

    # Write the blurred image to the video for the specified number of frames
    for _ in range(num_frames):
        video_writer.write(blurred_image)


def get_audio_length(audio_path):
    """
    Get the length of an audio file in seconds.

    Parameters:
    - audio_path: Path to the audio file.

    Returns:
    - Length of the audio file in seconds.
    """
    with wave.open(audio_path, 'r') as audio_file:
        frames = audio_file.getnframes()
        rate = audio_file.getframerate()
        duration = frames / float(rate)
    return duration


def create_video_from_images(book, animation_types, blur_duration=3, fps=24):
    """
    Create a video from images in a folder, applying an animation (pan or zoom) and then a blur effect.

    Parameters:
    - folder_path: Path to the folder containing images.
    - output_folder_path: Path to save the output videos.
    - narration_folder_path: Path to the folder containing narration audio files.
    - animation_types: List of animation types to apply for each image ('pan' or 'zoom').
    - blur_duration: Duration of the blur effect in seconds (default is 3).
    - fps: Frames per second for the video (default is 24).
    """
    # Paths
    folder_path = f"./data/{book}/image"
    output_folder_path = f"./data/{book}/video"
    narration_folder_path = f"./data/{book}/audio/speech"
    json_folder = f"./data/{book}/json"

    # Ensure the directory exists, create it if it doesn't
    os.makedirs(output_folder_path, exist_ok=True)

    # Get list of image files in the folder
    image_files = [os.path.join(folder_path, f) for f in os.listdir(folder_path) if f.endswith(('.png', '.jpg', '.jpeg'))]
    image_files.sort()  # Sort to maintain order

    # Check if the number of animations matches the number of images
    if len(image_files) != len(animation_types):
        raise ValueError("The number of animation types must match the number of images in the folder.")

    # Read the first image to get dimensions
    if len(image_files) == 0:
        raise ValueError("No images found in the specified folder.")
    
    first_image = cv2.imread(image_files[0])
    height, width, _ = first_image.shape

    # Process each image
    for idx, (image_path, animation_type) in enumerate(zip(image_files, animation_types)):
        image = cv2.imread(image_path)
        image_name = os.path.splitext(os.path.basename(image_path))[0]

        # Define video writer for the zoom/pan animation
        output_video_path_animation = os.path.join(output_folder_path, f"step_{idx}_desc.mp4")
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        video_writer_animation = cv2.VideoWriter(output_video_path_animation, fourcc, fps, (width, height))

        # Get narration file length for the current image animation
        animation_narration_file = next((os.path.join(narration_folder_path, f) for f in os.listdir(narration_folder_path) if f.startswith(f"step_{idx}_desc")), None)
        if not animation_narration_file or not os.path.exists(animation_narration_file):
            raise ValueError(f"Narration file {animation_narration_file} not found.")
        animation_duration = get_audio_length(animation_narration_file)

        # Apply the chosen animation
        num_frames_animation = int(fps * animation_duration)
        if animation_type == 'pan':
            generate_pan_animation(image, video_writer_animation, num_frames=num_frames_animation)
        elif animation_type == 'zoom':
            generate_zoom_animation(image, video_writer_animation, num_frames=num_frames_animation)
        else:
            raise ValueError("Unsupported animation type. Use 'pan' or 'zoom'.")

        # Release the video writer for the animation
        video_writer_animation.release()

        # Define video writer for the blur animation
        output_video_path_blur = os.path.join(output_folder_path, f"step_{idx+1}_title.mp4")
        video_writer_blur = cv2.VideoWriter(output_video_path_blur, fourcc, fps, (width, height))

        # Get blur narration length if available
        blur_narration_file = next((os.path.join(narration_folder_path, f) for f in os.listdir(narration_folder_path) if f.startswith(f"step_{idx+1}_title")), None)
        if blur_narration_file and os.path.exists(blur_narration_file):
            blur_duration = get_audio_length(blur_narration_file)
        else:
            blur_duration = 5

        # Apply blur effect
        num_frames_blur = int(fps * blur_duration)
        generate_blur_animation(image, video_writer_blur, num_frames=num_frames_blur)

        # Release the video writer for the blur animation
        video_writer_blur.release()

    add_subtitles_and_voiceover(output_folder_path, narration_folder_path, json_folder, fps)


def add_subtitles_and_voiceover(video_folder_path, narration_folder_path, json_folder, fps=24):
    """
    Add subtitles and voiceover to each video in the output folder.

    Parameters:
    - video_folder_path: Path to the folder containing the videos.
    - narration_folder_path: Path to the folder containing narration audio files.
    - fps: Frames per second for the video (default is 24).
    """
    video_files = [f for f in os.listdir(video_folder_path) if f.endswith('.mp4')]
    video_files.sort()

    # Get json with subtitles
    # Iterate through each JSON file in the json folder
    # There should be one in fact
    for json_file_name in os.listdir(json_folder):
        if json_file_name.endswith('.json'):
            json_filepath = os.path.join(json_folder, json_file_name)
            
            # Load the JSON file
            with open(json_filepath, 'r') as json_file:
                data = json.load(json_file)
                 
    for video_file in video_files:
        video_path = os.path.join(video_folder_path, video_file)
        narration_file = next((os.path.join(narration_folder_path, f) for f in os.listdir(narration_folder_path) if f.startswith(video_file.split('.')[0])), None)
        # Load video
        background_clip = VideoFileClip(video_path)
        final_clip = VideoFileClip(video_path)
        if narration_file:
            # Load video
            voice = AudioFileClip(narration_file)

            # Text to display
            video_filename = video_file.split('.')[0]
            step_idx = int(video_filename.split("_")[1])
            step_txt = 'description' if video_filename.split("_")[2] == 'desc' else 'title'
            text = data['steps'][step_idx][step_txt]

            # Split text into words
            words = text.split()

            # Calculate start times and durations for each word based on 13 characters per second
            start_times = []
            durations = []
            start_time = 0.0

            for word in words:
                duration = len(word) / 18.0  # Duration for each word
                start_times.append(start_time)
                durations.append(duration)
                start_time += duration

            total_duration = start_time

            # Function to calculate the position of each word
            def make_pos_fn(i):
                def pos_fn(t):
                    pos = ('center', background_clip.h + 1000)  # Word not yet started or two words before; position off-screen
                    displayed_words = [j for j, s in enumerate(start_times) if s <= t]
                    if i in displayed_words:
                        index_in_displayed = displayed_words.index(i)
                        if len(displayed_words) - index_in_displayed <= 2:
                            y = background_clip.h / 2 - (len(displayed_words) - index_in_displayed - 1) * 60
                            pos = ('center', y)
                    return pos
                return pos_fn

            # Create TextClips for each word
            word_clips = []
            for i, word in enumerate(words):
                text_clip = TextClip(word, font='Arial-Bold', fontsize=75, color='white')
                txt_bg = ColorClip(size=text_clip.size, color=(0, 0, 0)).set_opacity(0.75)
                txt_clip = CompositeVideoClip([txt_bg, text_clip]).set_duration(total_duration).set_pos(make_pos_fn(i))
                word_clips.append(txt_clip)

            # Create the final composite video
            final_clip = CompositeVideoClip([background_clip] + word_clips, size=(background_clip.w, background_clip.h))
            final_clip = final_clip.set_duration(max(background_clip.duration, total_duration))
            final_clip = final_clip.set_audio(voice)

        # Write the output video
        output_video_path = os.path.join(video_folder_path, f"sub_{video_file}")
        final_clip.write_videofile(output_video_path, fps=fps)


def concatenate_videos_with_audio_normalization(book, prefix="sub_"):
    """
    Concatenates multiple MP4 videos starting with a specific prefix into one video.
    Adjusts the audio volume of each clip so that all clips have the same loudness,
    equal to the loudest one.

    Parameters:
        input_folder (str): Path to the folder containing the videos.
        output_file (str): Name of the output concatenated video file.
        prefix (str): Prefix of the files to include in the concatenation.
    """
    try:
        # Paths
        input_folder = f"./data/{book}/video"
        output_file = f"./data/{book}/{book}.mp4"

        # Get list of files starting with the given prefix and ending with .mp4
        files = [f for f in os.listdir(input_folder) if f.startswith(prefix) and f.endswith('.mp4')]
        if not files:
            logging.error("No video files found with prefix '{}' in folder '{}'.".format(prefix, input_folder))
            return
        
        # Sort the files by step number and type (title or description)
        def sort_key(filename):
            parts = filename.split('_')
            step_number = int(parts[2]) # prefix_step_nb_...
            type_priority = 0 if 'title' in filename else 1 if 'desc' in filename else 2
            return (step_number, type_priority, filename)
        
        files.sort(key=sort_key)

        # Create full paths to the video files
        video_paths = [os.path.join(input_folder, f) for f in files]
        
        # Analyze the loudness of each clip
        audio_loudness = [{'video': video, 'loudness': None} for video in video_paths]
        max_loudness = 0
        for idx, video in enumerate(video_paths):
            try:
                audio = AudioSegment.from_file(video)
                loudness = audio.dBFS
                audio_loudness[idx]['loudness'] = loudness
                # Find the maximum loudness (loudest clip)
                if loudness > max_loudness:
                    max_loudness = loudness
            except IndexError:
                continue

        # Load the video clips and adjust audio volume
        clips = []
        for video_loudness in audio_loudness:
            try:
                video = video_loudness['video']
                loudness = video_loudness['loudness']
                clip = VideoFileClip(video)
                if clip.audio is not None:
                    # Calculate the gain needed to match the loudest clip
                    dB_difference = max_loudness - loudness
                    gain = 0.25 * 10 ** (dB_difference / 20) # Pct of the loudest
                    # Adjust the audio volume
                    clip = clip.volumex(gain)
                clips.append(clip)
            except Exception as e:
                logging.error("Error loading video '{}': {}".format(video, e))
        if not clips:
            logging.error("No valid video clips to concatenate.")
            return
        # Concatenate the clips
        final_clip = concatenate_videoclips(clips, method="compose")
        # Write the output video file
        final_clip.write_videofile(output_file, codec="libx264", audio_codec="aac")
    except Exception as e:
        logging.error("An error occurred during concatenation: {}".format(e))
    finally:
        # Close the clips to release resources
        try:
            final_clip.close()
        except:
            pass
        for clip in clips:
            try:
                clip.close()
            except:
                pass