// Mallas de columnas (010, contorno de tinta en 011). Solo se importa al abrir el globo, junto a globe.gl y three.
//
// 011: cada columna lleva un contorno de tinta (casco invertido: la misma geometría, algo más
// gruesa, pintada solo por detrás). Así una columna amarilla se lee sobre papel claro sin
// cambiar la escala de profundidad. Sigue siendo una sola malla instanciada por capa.
import type { GlobeInstance } from 'globe.gl';
import * as THREE from 'three';
import { ALTURA_COLUMNA_ND, PuntoGlobo } from '../../puro/globo';

const EJE_Y = new THREE.Vector3(0, 1, 0);
/** Aguja: base algo más ancha que la punta, para que se lea como columna y no como palo. */
const GEO = new THREE.CylinderGeometry(0.35, 1, 1, 6);
GEO.translate(0, 0.5, 0);
/** Grosor del contorno respecto a la columna. */
const GROSOR_CONTORNO = 1.9;

export interface TemaMallas {
  aro: string;
  contorno: string;
  /** Intensidad de las luces añadidas: en papel, menos, para no quemar la textura clara. */
  luz: number;
}

export interface CapaColumnas {
  mesh: THREE.InstancedMesh;
  contorno: THREE.InstancedMesh;
  aro: THREE.Mesh;
  puntos: PuntoGlobo[];
  luces: { ambiente: THREE.AmbientLight; dir: THREE.DirectionalLight };
}

function nuevaMalla(material: THREE.Material, capacidad: number, orden: number): THREE.InstancedMesh {
  const mesh = new THREE.InstancedMesh(GEO, material, Math.max(capacidad, 1));
  mesh.frustumCulled = false;
  mesh.renderOrder = orden;
  mesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
  mesh.count = 0;
  return mesh;
}

const materialColumnas = () => new THREE.MeshLambertMaterial({ toneMapped: false });
const materialContorno = (color = '#1a1a1a') =>
  new THREE.MeshBasicMaterial({ color, side: THREE.BackSide, toneMapped: false });

export function crearCapaColumnas(globo: GlobeInstance): CapaColumnas {
  const mesh = nuevaMalla(materialColumnas(), 1, 2);
  const contorno = nuevaMalla(materialContorno(), 1, 1);
  const aroGeo = new THREE.RingGeometry(0.85, 1.2, 40);
  const aroMat = new THREE.MeshBasicMaterial({
    color: 0xffffff,
    side: THREE.DoubleSide,
    transparent: true,
    opacity: 0.95,
    toneMapped: false,
  });
  const aro = new THREE.Mesh(aroGeo, aroMat);
  aro.visible = false;
  aro.renderOrder = 3;
  const ambiente = new THREE.AmbientLight(0xffffff, 0.7);
  const dir = new THREE.DirectionalLight(0xffffff, 1.05);
  dir.position.set(-0.5, 0.8, 1);
  for (const o of [contorno, mesh, aro, ambiente, dir]) globo.scene().add(o);
  return { mesh, contorno, aro, puntos: [], luces: { ambiente, dir } };
}

/** Colores y luces según el tema (011). */
export function aplicarTemaMallas(capa: CapaColumnas, t: TemaMallas): void {
  (capa.aro.material as THREE.MeshBasicMaterial).color.set(t.aro);
  (capa.contorno.material as THREE.MeshBasicMaterial).color.set(t.contorno);
  capa.luces.ambiente.intensity = 0.7 * t.luz;
  capa.luces.dir.intensity = 1.05 * t.luz;
}

function orientar(dummy: THREE.Object3D, x: number, y: number, z: number): void {
  dummy.position.set(x, y, z);
  dummy.quaternion.setFromUnitVectors(EJE_Y, dummy.position.clone().normalize());
}

function asegurarCapacidad(capa: CapaColumnas, globo: GlobeInstance, n: number): void {
  const capacidad = capa.mesh.instanceMatrix.array.length / 16;
  if (n <= capacidad) return;
  const escena = globo.scene();
  const colorContorno = (capa.contorno.material as THREE.MeshBasicMaterial).color.getStyle();
  for (const viejo of [capa.mesh, capa.contorno]) {
    escena.remove(viejo);
    viejo.dispose();
  }
  capa.mesh = nuevaMalla(materialColumnas(), n, 2);
  capa.contorno = nuevaMalla(materialContorno(colorContorno), n, 1);
  escena.add(capa.contorno);
  escena.add(capa.mesh);
}

export function actualizarColumnas(
  capa: CapaColumnas,
  globo: GlobeInstance,
  puntos: PuntoGlobo[],
  seleccionado: string | null,
): void {
  const n = puntos.length;
  asegurarCapacidad(capa, globo, n);
  capa.puntos = puntos;
  capa.mesh.count = n;
  capa.contorno.count = n;
  const dummy = new THREE.Object3D();
  const color = new THREE.Color();
  for (let i = 0; i < n; i++) {
    const p = puntos[i];
    const base = globo.getCoords(p.lat, p.lng, 0);
    const techo = globo.getCoords(p.lat, p.lng, Math.max(p.altura, ALTURA_COLUMNA_ND));
    orientar(dummy, base.x, base.y, base.z);
    const alto = Math.hypot(techo.x - base.x, techo.y - base.y, techo.z - base.z);
    const radioGlobo = Math.hypot(base.x, base.y, base.z) || 1;
    const grosor = radioGlobo * (0.0022 + Math.min(p.altura, 0.25) * 0.012);
    dummy.scale.set(grosor, alto, grosor);
    dummy.updateMatrix();
    capa.mesh.setMatrixAt(i, dummy.matrix);
    dummy.scale.set(grosor * GROSOR_CONTORNO, alto + grosor * 0.6, grosor * GROSOR_CONTORNO);
    dummy.updateMatrix();
    capa.contorno.setMatrixAt(i, dummy.matrix);
    color.set(p.color);
    capa.mesh.setColorAt(i, color);
  }
  capa.mesh.instanceMatrix.needsUpdate = true;
  capa.contorno.instanceMatrix.needsUpdate = true;
  if (capa.mesh.instanceColor) capa.mesh.instanceColor.needsUpdate = true;

  const sel = seleccionado ? puntos.find((p) => p.id === seleccionado) : undefined;
  if (!sel) {
    capa.aro.visible = false;
    return;
  }
  const pos = globo.getCoords(sel.lat, sel.lng, 0.006);
  orientar(capa.aro, pos.x, pos.y, pos.z);
  const s = Math.hypot(pos.x, pos.y, pos.z) * 0.012;
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
  const escena = globo.scene();
  for (const o of [capa.mesh, capa.contorno, capa.aro, capa.luces.ambiente, capa.luces.dir]) escena.remove(o);
  capa.mesh.dispose();
  capa.contorno.dispose();
  (capa.contorno.material as THREE.Material).dispose();
  capa.aro.geometry.dispose();
  (capa.aro.material as THREE.Material).dispose();
}
