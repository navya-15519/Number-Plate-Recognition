
const video = document.getElementById("video");
const canvas = document.getElementById("canvas");

const startButton = document.getElementById("startCamera");
const captureButton = document.getElementById("capture");
const stopButton = document.getElementById("stopCamera");

const result = document.getElementById("webcamResult");

let cameraStream = null;

startButton.addEventListener("click", async () => {
    try {
        cameraStream = await navigator.mediaDevices.getUserMedia({
            video: true,
            audio: false
        });

        video.srcObject = cameraStream;
        result.textContent = "Camera started successfully!";
    } catch (error) {
        result.textContent = "Unable to access webcam. Check permission.";
    }
});

captureButton.addEventListener("click", async () => {

    if (!cameraStream) {
        result.textContent = "Please start the webcam first.";
        return;
    }

    if (!video.videoWidth) {
        result.textContent = "Camera is not ready yet.";
        return;
    }

    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;

    const context = canvas.getContext("2d");
    context.drawImage(video, 0, 0);

    const image = canvas.toDataURL("image/jpeg", 0.8);

    result.textContent = "Recognizing number plate...";

    try {
        const response = await fetch("/recognize-frame", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ image: image })
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || "Recognition failed");
        }

        result.textContent = "Detected Number: " + data.number;

    } catch (error) {
        result.textContent = error.message;
    }
});

stopButton.addEventListener("click", () => {

    if (cameraStream) {
        cameraStream.getTracks().forEach(track => track.stop());
        cameraStream = null;
    }

    video.srcObject = null;
    result.textContent = "Camera stopped.";
});
