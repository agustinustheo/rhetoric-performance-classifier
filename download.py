from imutils.video import VideoStream
from keras.preprocessing import image
import tensorflow as tf
import numpy as np
import youtube_dl
import imutils
import json
import time
import cv2
import os

try:
	# Define paths
	base_dir = os.path.dirname(__file__)
	prototxt_path = os.path.join(base_dir + 'model/deploy.prototxt')
	caffemodel_path = os.path.join(base_dir + 'model/weights.caffemodel')
	model = tf.keras.models.load_model('model/cnn_face_expression.model')
	emotions = ('angry', 'disgust', 'fear', 'happy', 'sad', 'surprise', 'neutral')
	video_url = 'https://www.youtube.com/watch?v=dGuheGml_wQ'

	ydl_opts = {
		'format' : '133',
		'outtmpl': '%(id)s.mp4'
	}

	# create youtube-dl object
	ydl = youtube_dl.YoutubeDL(ydl_opts)
	with youtube_dl.YoutubeDL(ydl_opts) as asd:
		asd.download([video_url])

	# set video url, extract video information
	info_dict = ydl.extract_info(video_url, download=False)

	# get video formats available
	formats = info_dict.get('formats',None)
	duration = info_dict.get('duration',None)

	flag_for_testing = 0

	def secondMaxEmotion(predictions, max_index):
		emotions_index = 0
		secondary_emotion_index = 0
		max_emotion_num = -1
		for x in predictions:
			if (max_emotion_num < x) and (emotions_index != max_index):
				secondary_emotion_index = emotions_index
				max_emotion_num = x
			emotions_index += 1
			
		for x in predictions:
			if (max_emotion_num < x) and (emotions_index != max_index):
				max_emotion_num = x
			emotions_index += 1

		return secondary_emotion_index

	for f in formats:
		if flag_for_testing == 1:
			break

		# I want the lowest resolution, so I set resolution as 144p
		if f.get('format_note',None) == '144p':
			
			#get the video url
			url = f.get('url',None)
			ext = f.get('ext',None)

			# load our serialized model from disk
			print("[INFO] loading model...")
			net = cv2.dnn.readNetFromCaffe(prototxt_path, caffemodel_path)

			# initialize the video stream and allow the cammera sensor to warmup
			print("[INFO] starting video stream...")
			vs = cv2.VideoCapture(str(info_dict["id"]) + "." + str(ext))

			fps = vs.get(cv2.CAP_PROP_FPS)

			frame_count = 0
			emotion_timestamp = []
			emotion_start = -1
			curr_emotion = ""
			# loop over the frames from the video stream
			while True:
				frame_count = frame_count + 1
				# grab the frame from the threaded video stream and resize it
				# to have a maximum width of 400 pixels
				ret, frame = vs.read()
				
				# check if frame is empty
				if not ret:
					break
				
				# grab the frame dimensions and convert it to a blob
				(h, w) = frame.shape[:2]
				blob = cv2.dnn.blobFromImage(cv2.resize(frame, (300, 300)), 1.0,
					(300, 300), (104.0, 177.0, 123.0))
			
				# pass the blob through the network and obtain the detections and
				# predictions
				net.setInput(blob)
				detections = net.forward()

				sum_confidence = 0
				# loop over the detections
				for i in range(0, detections.shape[2]):
					# extract the confidence (i.e., probability) associated with the
					# prediction
					confidence = detections[0, 0, i, 2]

					# filter out weak detections by ensuring the `confidence` is
					# greater than the minimum confidence
					if confidence < 0.5:
						continue

					sum_confidence = sum_confidence + confidence
					# compute the (x, y)-coordinates of the bounding box for the
					# object
					box = detections[0, 0, i, 3:7] * np.array([w, h, w, h])
					(startX, startY, endX, endY) = box.astype("int")
			
					# draw the bounding box of the face along with the associated
					# probability
					text = "{:.2f}%".format(confidence * 100)
					y = startY - 10 if startY - 10 > 10 else startY + 10

					# draw rectangle on face
					cv2.rectangle(frame, (startX, startY), (endX, endY), (0, 0, 255), 2)
					# write the percentage text
					# cv2.putText(frame, text, (startX, y), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 255), 2)

				if sum_confidence < 0.6:
					emotion_end = float(frame_count)/fps
					# if face detection confidence is below 50% and the face detected index is not 0 then append face detected duration to tense_timestamp
					if emotion_start != -1:
						emotion_timestamp.append( {'start_time': emotion_start , 'end_time': emotion_end  , 'emotion': curr_emotion} )
						emotion_start = -1

				else:
					detected_face = frame[int(startY):int(startY+endY), int(startX):int(startX+endX)] #crop detected face
					detected_face = cv2.cvtColor(detected_face, cv2.COLOR_BGR2GRAY) #transform to gray scale
					detected_face = cv2.resize(detected_face, (48, 48)) #resize to 48x48

					img_pixels = image.img_to_array(detected_face)
					img_pixels = np.expand_dims(img_pixels, axis = 0)
					
					img_pixels /= 255
					
					predictions = model.predict(img_pixels)
					
					#find max indexed array
					max_index = np.argmax(predictions[0])
					secondary_max_index = secondMaxEmotion(predictions[0], max_index)
					
					emotion = emotions[max_index]
					secondary_emotion = emotions[secondary_max_index]

					if (emotion == 'fear' and secondary_emotion == 'sad') or (emotion == 'sad' and secondary_emotion == 'fear'):
						emotion = 'tense'
					elif(emotion == 'angry' and secondary_emotion == 'sad') or (emotion == 'sad' and secondary_emotion == 'angry'):
						emotion = 'serious'

					# if face detection confidence is above 50% and the face detected index is 0 then set new face detected index
					if emotion_start == -1:
						emotion_start = float(frame_count)/fps
						curr_emotion = emotion
					# if emotion change then add anger_timestamp
					elif curr_emotion != emotion and emotion_start != -1:
						emotion_end = float(frame_count)/fps
						emotion_timestamp.append( {'start_time': emotion_start ,'end_time': emotion_end ,'emotion': emotion} )
						emotion_start = -1
						curr_emotion = emotion
					# if video end then add anger_timestamp
					if frame_count == fps and emotion_start != -1:
						emotion_end = float(frame_count)/fps
						emotion_timestamp.append( {'start_time': emotion_start ,'end_time': emotion_end ,'emotion': curr_emotion} )
						break
					
					# write emotion text on image
					cv2.putText(frame, emotion, (int(startX), int(startY)), cv2.FONT_HERSHEY_SIMPLEX, 1, (255,255,255), 2)

				flag_for_testing = 1

				# show the output frame
				cv2.imshow("Frame", frame)
				key = cv2.waitKey(1) & 0xFF

				# if the `q` key was pressed, break from the loop
				if key == ord("q"):
					break

		if flag_for_testing == 1:
			break
			
	vs.release()
	# do a bit of cleanup
	cv2.destroyAllWindows()

	tense_count = 0
	micro_tense_count = 0
	anger_count = 0
	micro_anger_count = 0
	for x in emotion_timestamp:
		if x["end_time"] - x["start_time"] >= 0.5 and x["emotion"] == 'tense':
			tense_count += 1

		if x["end_time"] - x["start_time"] >= 0.1 and x["end_time"] - x["start_time"] < 0.5 and x["emotion"] == 'tense':
			micro_tense_count += 1
		
		if x["end_time"] - x["start_time"] >= 0.5 and x["emotion"] == 'angry':
			anger_count += 1
		
		if x["end_time"] - x["start_time"] >= 0.1 and x["end_time"] - x["start_time"] < 0.5 and x["emotion"] == 'angry':
			micro_anger_count += 1

	
	return_json = json.dumps(
		{
			"result": 
			{
				"tense_count": tense_count,
				"anger_count": anger_count,
				"micro_tense_count": micro_tense_count,
				"micro_anger_count": micro_anger_count
			}
		}
	)

	print(return_json)
	os.remove(str(info_dict["id"]) + "."  + str(ext))

except Exception as e:
	err_msg = "Error: " + str(e)

	return_json = json.dumps(
		{
			"error": err_msg
		}
	)

	print(return_json)
