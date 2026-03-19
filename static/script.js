function startCam(){

let cam=document.getElementById("camera")

cam.src="/video"

}

function stopCam(){

fetch("/stop_camera")

let cam=document.getElementById("camera")

cam.src=""

}

function showText(){

fetch("/get_text")

.then(res=>res.json())

.then(data=>{

document.getElementById("output").innerText=data.text

})

}

function readText(){

let text=document.getElementById("output").innerText

let speech=new SpeechSynthesisUtterance(text)

speechSynthesis.speak(speech)

}

function newConversation(){

fetch("/clear_text")

document.getElementById("output").innerText=""

}
function startCam(){

let cam=document.getElementById("camera")

cam.src="/video"

}


function stopCam(){

fetch("/stop_camera")

let cam=document.getElementById("camera")

cam.src=""

}


function showText(){

fetch("/get_text")
.then(res=>res.json())
.then(data=>{

document.getElementById("output").innerText=data.text

})

}


function readText(){

let text=document.getElementById("output").innerText

let speech=new SpeechSynthesisUtterance(text)

speechSynthesis.speak(speech)

}


function newConversation(){

fetch("/clear_text")

document.getElementById("output").innerText=""

}


/* glowing camera border */

setInterval(()=>{

fetch("/hand_status")
.then(res=>res.json())
.then(data=>{

let camBox=document.getElementById("cameraBox")

if(data.hand){

camBox.classList.add("active")

}else{

camBox.classList.remove("active")

}

})

},500)