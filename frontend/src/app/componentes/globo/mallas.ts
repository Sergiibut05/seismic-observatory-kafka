// Mallas de columnas (010). Solo se importa al abrir el globo, junto a globe.gl y three.
import type { GlobeInstance } from 'globe.gl';
import * as THREE from 'three';
import { PuntoGlobo } from '../../puro/globo';

const COLOR_ARO = 0xffffff;
const EJE_Y = new THREE.Vector3(0, 1, 0);
const GEO = new THREE.CylinderGeometry(0.55, 0.85, 1, 8);
GEO.translate(0, 0.5, 0);

export interface CapaColumnas {
  mesh: THREE.InstancedMesh;
  aro: THREE.Mesh;
  puntos: PuntoGlobo[];
  luces: THREE.Light[];
}

function materialColumnas(): THREE.MeshLambertMaterial {
  return new THREE.MeshLambertMaterial({ toneMapped: false });
}

export function crearCapaColumnas(globo: GlobeInstance): CapaColumnas {
  const mesh = new THREE.InstancedMesh(GEO, materialColumnas(), 1);
  mesh.frustumCulled = false;
  mesh.renderOrder = 2;
  mesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
  mesh.count = 0;
  const aroGeo = new THREE.RingGeometry(0.85, 1.2, 40);
  const aroMat = new THREE.MeshBasicMaterial({
    color: COLOR_ARO,
    side: THREE.DoubleSide,
    transparent: true,
    opacity: 0.95,
    toneMapped: false,
  });
  const aro = new THREE.Mesh(aroGeo, aroMat);
  aro.visible = false;
  aro.renderOrder = 3;
  const ambiente = new THREE.AmbientLight(0xb8c4ff, 0.7);
  const dir = new THREE.DirectionalLight(0xffffff, 1.05);
  dir.position.set(-0.5, 0.8, 1);
  globo.scene().add(mesh);
  globo.scene().add(aro);
  globo.scene().add(ambiente);
  globo.scene().add(dir);
  return { mesh, aro, puntos: [], luces: [ambiente, dir] };
}

function orientar(dummy: THREE.Object3D, x: number, y: number, z: number): void {
  dummy.position.set(x, y, z);
  dummy.quaternion.setFromUnitVectors(EJE_Y, dummy.position.clone().normalize());
}

export function actualizarColumnas(
  capa: CapaColumnas,
  globo: GlobeInstance,
  puntos: PuntoGlobo[],
  seleccionado: string | null,
): void {
  const n = puntos.length;
  const capacidad = capa.mesh.instanceMatrix.array.length / 16;
  if (n > capacidad) {
    globo.scene().remove(capa.mesh);
    capa.mesh.dispose();
    const mesh = new THREE.InstancedMesh(GEO, materialColumnas(), Math.max(n, 1));
    mesh.frustumCulled = false;
    mesh.renderOrder = 2;
    mesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
    globo.scene().add(mesh);
    capa.mesh = mesh;
  }
  capa.puntos = puntos;
  capa.mesh.count = n;
  const dummy = new THREE.Object3D();
  const color = new THREE.Color();
  for (let i = 0; i < n; i++) {
    const p = puntos[i];
    const base = globo.getCoords(p.lat, p.lng, 0);
    const techo = globo.getCoords(p.lat, p.lng, Math.max(p.altura, 0.04));
    orientar(dummy, base.x, base.y, base.z);
    const alto = Math.hypot(techo.x - base.x, techo.y - base.y, techo.z - base.z);
    const radioGlobo = Math.hypot(base.x, base.y, base.z) || 1;
    const grosor = radioGlobo * (0.005 + Math.min(p.altura, 0.5) * 0.012);
    dummy.scale.set(grosor, alto, grosor);
    dummy.updateMatrix();
    capa.mesh.setMatrixAt(i, dummy.matrix);
    color.set(p.color);
    capa.mesh.setColorAt(i, color);
  }
  capa.mesh.instanceMatrix.needsUpdate = true;
  if (capa.mesh.instanceColor) capa.mesh.instanceColor.needsUpdate = true;

  const sel = seleccionado ? puntos.find((p) => p.id === seleccionado) : undefined;
  if (!sel) {
    capa.aro.visible = false;
    return;
  }
  const pos = globo.getCoords(sel.lat, sel.lng, 0.006);
  orientar(capa.aro, pos.x, pos.y, pos.z);
  const s = Math.hypot(pos.x, pos.y, pos.z) * 0.02;
  capa.aro.scale.set(s, s, s);
  capa.aro.visible = true;
}

export function recogerColumna(
  capa: CapaColumnas,
  globo: GlobeInstance,
  evento: MouseEvent,
): PuntoGlobo | null {
  if (!capa.puntos.length) return null;
  const canvas = globo.renderer().domElement;
  const rect = canvas.getBoundingClientRect();
  const mouse = new THREE.Vector2(
    ((evento.clientX - rect.left) / rect.width) * 2 - 1,
    -((evento.clientY - rect.top) / rect.height) * 2 + 1,
  );
  const raycaster = new THREE.Raycaster();
  raycaster.setFromCamera(mouse, globo.camera());
  const hits = raycaster.intersectObject(capa.mesh);
  const id = hits[0]?.instanceId;
  if (id === undefined) return null;
  return capa.puntos[id] ?? null;
}

export function destruirCapa(capa: CapaColumnas, globo: GlobeInstance): void {
  globo.scene().remove(capa.mesh);
  globo.scene().remove(capa.aro);
  for (const luz of capa.luces) globo.scene().remove(luz);
  capa.mesh.dispose();
  capa.aro.geometry.dispose();
  (capa.aro.material as THREE.Material).dispose();
}
