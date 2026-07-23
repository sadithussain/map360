/**
 * MapLibre custom layer that renders generated GLB meshes on the map.
 *
 * Each {@link MapObjectResponse} is loaded once (cached by object id) and
 * anchored at its real-world `lng`/`lat` using MapLibre's mercator transform,
 * so the mesh sits exactly where the contributed building was selected. Models
 * are normalized to a fixed real-world size and grounded so their base rests on
 * the map plane. The layer also supports a short-lived emissive "pulse" used to
 * highlight objects that have just appeared.
 */

import maplibregl from "maplibre-gl";
import type {
  CustomLayerInterface,
  CustomRenderMethodInput,
  Map as MapLibreMap,
} from "maplibre-gl";
import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";

import type { MapObjectResponse } from "./types";

export const GENERATED_MESHES_LAYER_ID = "generated-meshes";

/** Largest bounding-box dimension a placed mesh is scaled to, in meters. */
const TARGET_SIZE_METERS = 12;

/** How long a newly added object pulses, in milliseconds. */
const HIGHLIGHT_DURATION_MS = 4000;

/** Emissive tint applied while an object is highlighted. */
const HIGHLIGHT_COLOR = new THREE.Color("#4f46e5");

type HighlightMaterial = THREE.Material & {
  emissive?: THREE.Color;
  emissiveIntensity?: number;
};

type LoadedObject = {
  id: string;
  root: THREE.Object3D;
  /** Original emissive state per material, captured for highlight restore. */
  originalEmissive: Map<HighlightMaterial, { color: THREE.Color; intensity: number }>;
};

function hasEmissive(material: THREE.Material): material is HighlightMaterial {
  return "emissive" in material && (material as HighlightMaterial).emissive !== undefined;
}

/** Build the mercator transform matrix that anchors a model at a coordinate. */
function anchorMatrix(lng: number, lat: number): THREE.Matrix4 {
  const merc = maplibregl.MercatorCoordinate.fromLngLat([lng, lat], 0);
  const scale = merc.meterInMercatorCoordinateUnits();
  // Compose translate -> scale (y flipped for mercator) -> rotate GLB y-up to
  // MapLibre's z-up frame. This matches MapLibre's 3D-model custom layer.
  return new THREE.Matrix4()
    .makeTranslation(merc.x, merc.y, merc.z)
    .scale(new THREE.Vector3(scale, -scale, scale))
    .multiply(new THREE.Matrix4().makeRotationX(Math.PI / 2));
}

/**
 * Normalize a loaded GLB in place: scale so its largest dimension is
 * {@link TARGET_SIZE_METERS}, center it horizontally, and rest its base at y=0.
 */
function normalizeModel(model: THREE.Object3D): void {
  model.updateMatrixWorld(true);
  const box = new THREE.Box3().setFromObject(model);
  const size = box.getSize(new THREE.Vector3());
  const maxDim = Math.max(size.x, size.y, size.z);
  if (maxDim > 0) {
    model.scale.multiplyScalar(TARGET_SIZE_METERS / maxDim);
  }

  model.updateMatrixWorld(true);
  const scaledBox = new THREE.Box3().setFromObject(model);
  const center = scaledBox.getCenter(new THREE.Vector3());
  model.position.x -= center.x;
  model.position.z -= center.z;
  model.position.y -= scaledBox.min.y;
}

export class GeneratedMeshLayer implements CustomLayerInterface {
  readonly id = GENERATED_MESHES_LAYER_ID;
  readonly type = "custom" as const;
  readonly renderingMode = "3d" as const;

  private map: MapLibreMap | null = null;
  private renderer: THREE.WebGLRenderer | null = null;
  private readonly scene = new THREE.Scene();
  private readonly camera = new THREE.Camera();
  private readonly loader = new GLTFLoader();

  private readonly objects = new Map<string, LoadedObject>();
  private readonly loading = new Set<string>();
  private readonly highlightStart = new Map<string, number>();

  /** Latest desired objects, applied once the renderer is ready. */
  private desired: MapObjectResponse[] = [];

  onAdd(map: MapLibreMap, gl: WebGLRenderingContext | WebGL2RenderingContext): void {
    this.map = map;

    this.renderer = new THREE.WebGLRenderer({
      canvas: map.getCanvas(),
      context: gl,
      antialias: true,
    });
    this.renderer.autoClear = false;

    this.scene.add(new THREE.AmbientLight(0xffffff, 1.6));
    const sun = new THREE.DirectionalLight(0xffffff, 1.2);
    sun.position.set(0.5, 1, 0.5);
    this.scene.add(sun);

    this.syncObjects();
  }

  render(
    _gl: WebGLRenderingContext | WebGL2RenderingContext,
    options: CustomRenderMethodInput,
  ): void {
    if (!this.renderer) {
      return;
    }

    this.applyHighlights();

    this.camera.projectionMatrix = new THREE.Matrix4().fromArray(
      Array.from(options.defaultProjectionData.mainMatrix),
    );

    this.renderer.resetState();
    this.renderer.render(this.scene, this.camera);

    if (this.highlightStart.size > 0) {
      this.map?.triggerRepaint();
    }
  }

  onRemove(): void {
    for (const object of this.objects.values()) {
      this.disposeObject(object);
    }
    this.objects.clear();
    this.loading.clear();
    this.highlightStart.clear();
    this.renderer?.dispose();
    this.renderer = null;
    this.map = null;
  }

  /** Replace the set of objects shown, loading new ones and removing stale ones. */
  setObjects(objects: MapObjectResponse[]): void {
    this.desired = objects;
    if (this.renderer) {
      this.syncObjects();
    }
  }

  /** Start a short emissive pulse on a placed object (e.g. just added). */
  highlightObject(objectId: string): void {
    this.highlightStart.set(objectId, performance.now());
    this.map?.triggerRepaint();
  }

  private syncObjects(): void {
    const desiredIds = new Set(this.desired.map((object) => object.id));

    for (const [id, object] of this.objects) {
      if (!desiredIds.has(id)) {
        this.scene.remove(object.root);
        this.disposeObject(object);
        this.objects.delete(id);
        this.highlightStart.delete(id);
      }
    }

    for (const object of this.desired) {
      if (this.objects.has(object.id) || this.loading.has(object.id)) {
        continue;
      }
      this.loadObject(object);
    }
  }

  private loadObject(object: MapObjectResponse): void {
    this.loading.add(object.id);
    this.loader.load(
      object.mesh_url,
      (gltf) => {
        this.loading.delete(object.id);
        // The object may have been removed from the desired set while loading.
        if (!this.desired.some((candidate) => candidate.id === object.id)) {
          return;
        }

        const model = gltf.scene;
        normalizeModel(model);

        const root = new THREE.Object3D();
        root.add(model);
        root.matrixAutoUpdate = false;
        root.matrix.copy(anchorMatrix(object.lng, object.lat));
        // The custom projection matrix already frames the world; skip culling.
        root.traverse((child) => {
          child.frustumCulled = false;
        });

        const originalEmissive = new Map<
          HighlightMaterial,
          { color: THREE.Color; intensity: number }
        >();
        root.traverse((child) => {
          const mesh = child as THREE.Mesh;
          if (!mesh.isMesh) {
            return;
          }
          const materials = Array.isArray(mesh.material)
            ? mesh.material
            : [mesh.material];
          for (const material of materials) {
            if (material && hasEmissive(material) && material.emissive) {
              originalEmissive.set(material, {
                color: material.emissive.clone(),
                intensity: material.emissiveIntensity ?? 1,
              });
            }
          }
        });

        this.scene.add(root);
        this.objects.set(object.id, { id: object.id, root, originalEmissive });
        this.map?.triggerRepaint();
      },
      undefined,
      () => {
        // Loading failed (bad URL, CORS, corrupt GLB); drop it so a later
        // sync can retry. The rest of the map keeps rendering.
        this.loading.delete(object.id);
      },
    );
  }

  private applyHighlights(): void {
    if (this.highlightStart.size === 0) {
      return;
    }

    const now = performance.now();
    for (const [id, start] of this.highlightStart) {
      const object = this.objects.get(id);
      const elapsed = now - start;

      if (!object || elapsed >= HIGHLIGHT_DURATION_MS) {
        if (object) {
          this.restoreEmissive(object);
        }
        this.highlightStart.delete(id);
        continue;
      }

      // Ease-out sine pulse that fades as the highlight expires.
      const progress = elapsed / HIGHLIGHT_DURATION_MS;
      const pulse = Math.sin(progress * Math.PI * 4) * 0.5 + 0.5;
      const intensity = pulse * (1 - progress);
      for (const material of object.originalEmissive.keys()) {
        material.emissive?.copy(HIGHLIGHT_COLOR);
        material.emissiveIntensity = intensity;
      }
    }
  }

  private restoreEmissive(object: LoadedObject): void {
    for (const [material, original] of object.originalEmissive) {
      material.emissive?.copy(original.color);
      material.emissiveIntensity = original.intensity;
    }
  }

  private disposeObject(object: LoadedObject): void {
    object.root.traverse((child) => {
      const mesh = child as THREE.Mesh;
      if (!mesh.isMesh) {
        return;
      }
      mesh.geometry?.dispose();
      const materials = Array.isArray(mesh.material)
        ? mesh.material
        : [mesh.material];
      for (const material of materials) {
        material?.dispose();
      }
    });
  }
}
