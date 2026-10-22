// Nạp three.js (thư viện 3D, giấy phép MIT) cho cảnh "3D thật xoay 360°"
import * as THREE from 'three';
import { GLTFLoader } from './GLTFLoader.js';
window.THREE = THREE; window.GLTFLoader = GLTFLoader;
window.dispatchEvent(new Event('three-ready'));
