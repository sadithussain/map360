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
import { RoomEnvironment } from "three/examples/jsm/environments/RoomEnvironment.js";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";

import type { MapObjectResponse } from "./types";

export const GENERATED_MESHES_LAYER_ID = "generated-meshes";

/**
 * Largest bounding-box dimension a placed mesh is scaled to when we cannot
 * determine the underlying stock building's height. Deliberately aggressive so
 * the generated mesh dominates typical low-rise gray extrusions (Option B).
 */
const FALLBACK_TARGET_SIZE_METERS = 20;

/**
 * Extra scale applied over the stock building's height so the mesh envelops
 * (rather than merely matches) the gray extrusion it sits on, "capping" it
 * instead of hiding the shared-osm_id building (which erased whole terraces).
 */
const COVER_SCALE = 1.15;

/**
 * Vertical lift (meters) applied after grounding so the mesh sits above the map
 * plane / stock extrusion base, avoiding z-fighting speckle against MapLibre's
 * shared depth buffer in ``renderingMode: "3d"``.
 */
const GROUND_LIFT_METERS = 1.0;

/**
 * Extrusion/footprint layers queried to estimate the stock building height
 * under a pin, most specific first. Only those present on the map are used.
 */
const STOCK_HEIGHT_LAYERS = [
  "building-3d",
  "grey-3d-buildings",
  "building",
] as const;

/** Pixel padding around the pin when hit-testing stock building features. */
const STOCK_QUERY_PADDING_PX = 6;

/** Assumed meters per OSM building level when only a level count is present. */
const METERS_PER_LEVEL = 3;

/** Metalness ceiling; TRELLIS exports often over-report metalness which, */
/** without a full IBL, renders near-black. */
const MAX_METALNESS = 0.25;

/** Roughness floor so surfaces still catch diffuse/environment light. */
const MIN_ROUGHNESS = 0.4;

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
  /** Anchor coordinates, kept so the matrix can be rebuilt on heading change. */
  lng: number;
  lat: number;
  /** Heading (deg) currently baked into {@link modelMatrix}. */
  heading: number;
  /**
   * Uniform user scale multiplier currently applied to {@link root}, on top of
   * the client-side auto-fit baked into the model's own local scale.
   */
  scale: number;
  /**
   * MapLibre model matrix (mercator translate/scale/rotate). Composed with the
   * per-frame view-projection matrix at render time instead of being baked onto
   * {@link root}, so the mesh stays in meter space and avoids Float32 collapse.
   */
  modelMatrix: THREE.Matrix4;
  /** Original emissive state per material, captured for highlight restore. */
  originalEmissive: Map<HighlightMaterial, { color: THREE.Color; intensity: number }>;
};

function hasEmissive(material: THREE.Material): material is HighlightMaterial {
  return "emissive" in material && (material as HighlightMaterial).emissive !== undefined;
}

/** Whether to emit one-shot mesh diagnostics (dev builds only). */
const MESH_DEBUG: boolean =
  typeof import.meta !== "undefined" && Boolean(import.meta.env?.DEV);

/**
 * Build the MapLibre model matrix that anchors a model at a coordinate.
 *
 * This matrix is NOT applied to the Three.js object. It is composed with
 * MapLibre's per-frame view-projection matrix at render time
 * (`projectionMatrix = mainMatrix * modelMatrix`), exactly like MapLibre's
 * official three.js example. Meshes therefore stay in meter-scale local space
 * in the scene; if we instead baked this (mercator meters ~= 2.5e-8) onto the
 * object's world matrix, a 12 m building would collapse into ~1e-7 mercator
 * units around an absolute coordinate ~0.5, which Float32 cannot resolve -
 * producing the "static textured blob".
 */
function anchorMatrix(lng: number, lat: number, headingDeg = 0): THREE.Matrix4 {
  const merc = maplibregl.MercatorCoordinate.fromLngLat([lng, lat], 0);
  const scale = merc.meterInMercatorCoordinateUnits();
  // Manual orientation: yaw around the model's own up axis (GLB Y) applied
  // before the axis conversion, so it becomes a rotation about the world
  // vertical after RotationX(π/2). Negated so increasing heading turns the
  // building clockwise when viewed from above (i.e. degrees clockwise from
  // north), matching how users read a compass dial.
  const headingRad = THREE.MathUtils.degToRad(headingDeg);
  // Official MapLibre composition: translate to mercator position, scale meters
  // to mercator units with a flipped Y (mercator Y grows south), then rotate
  // GLB y-up into MapLibre's z-up frame. The negative Y is safe here because
  // the reflection lives in the projection matrix, not on the Three.js object,
  // so object winding / FrontSide culling are unaffected.
  return new THREE.Matrix4()
    .makeTranslation(merc.x, merc.y, merc.z)
    .scale(new THREE.Vector3(scale, -scale, scale))
    .multiply(new THREE.Matrix4().makeRotationX(Math.PI / 2))
    .multiply(new THREE.Matrix4().makeRotationY(-headingRad));
}

/** Parse a numeric height-like property, tolerating strings and nullish. */
function parseNumeric(value: unknown): number | null {
  const parsed = typeof value === "string" ? Number.parseFloat(value) : value;
  return typeof parsed === "number" && Number.isFinite(parsed) ? parsed : null;
}

/** Extract a building height (meters) from a rendered feature's properties. */
function featureHeightMeters(properties: Record<string, unknown> | null): number | null {
  if (!properties) {
    return null;
  }
  const direct = parseNumeric(properties.render_height) ?? parseNumeric(properties.height);
  if (direct != null && direct > 0) {
    return direct;
  }
  const levels =
    parseNumeric(properties.render_levels) ?? parseNumeric(properties.levels);
  if (levels != null && levels > 0) {
    return levels * METERS_PER_LEVEL;
  }
  return null;
}

/**
 * Estimate the height (meters) of the stock building extrusion under a pin by
 * hit-testing the rendered extrusion/footprint layers. Returns the max finite
 * positive height among features hit near the pin, or ``null`` when nothing is
 * rendered there or no height property is available. Fill-extrusion picking is
 * flaky at a single pixel under pitch, so a small padded bbox is queried too.
 */
function queryStockBuildingHeight(
  map: MapLibreMap,
  lng: number,
  lat: number,
): number | null {
  const layers = STOCK_HEIGHT_LAYERS.filter((id) => map.getLayer(id));
  if (layers.length === 0) {
    return null;
  }

  const px = map.project([lng, lat]);
  const bbox: [maplibregl.PointLike, maplibregl.PointLike] = [
    [px.x - STOCK_QUERY_PADDING_PX, px.y - STOCK_QUERY_PADDING_PX],
    [px.x + STOCK_QUERY_PADDING_PX, px.y + STOCK_QUERY_PADDING_PX],
  ];

  let maxHeight: number | null = null;
  const collect = (features: maplibregl.MapGeoJSONFeature[]): void => {
    for (const feature of features) {
      const height = featureHeightMeters(
        (feature.properties ?? null) as Record<string, unknown> | null,
      );
      if (height != null && (maxHeight == null || height > maxHeight)) {
        maxHeight = height;
      }
    }
  };

  try {
    collect(map.queryRenderedFeatures(px, { layers }));
    collect(map.queryRenderedFeatures(bbox, { layers }));
  } catch {
    // queryRenderedFeatures can throw if a layer/source is mid-update; treat
    // as "unknown height" and fall back to the aggressive default.
    return null;
  }

  return maxHeight;
}

/**
 * Choose the target size (meters) the mesh's largest dimension should scale to
 * so that, after uniform normalization, its vertical extent covers the stock
 * building height by {@link COVER_SCALE}. Falls back to
 * {@link FALLBACK_TARGET_SIZE_METERS} when the height is unknown, and never
 * returns less than that floor so short sheds still dominate low-rise tiles.
 */
function targetSizeForStock(
  modelSize: THREE.Vector3,
  stockHeight: number | null,
): number {
  const maxDim = Math.max(modelSize.x, modelSize.y, modelSize.z);
  if (maxDim <= 0) {
    return FALLBACK_TARGET_SIZE_METERS;
  }
  if (stockHeight == null || stockHeight <= 0) {
    return FALLBACK_TARGET_SIZE_METERS;
  }

  // After uniform scale S = target / maxDim, the mesh height becomes
  // modelSize.y * S. Require modelSize.y * S >= stockHeight * COVER_SCALE, so
  // target >= stockHeight * COVER_SCALE * (maxDim / modelSize.y).
  const heightDim = Math.max(modelSize.y, 1e-6);
  const heightDriven = stockHeight * COVER_SCALE * (maxDim / heightDim);
  return Math.max(FALLBACK_TARGET_SIZE_METERS, heightDriven);
}

/** Bounding-box / scale figures captured while normalizing, for diagnostics. */
type NormalizeReport = {
  preMin: THREE.Vector3;
  preMax: THREE.Vector3;
  preSize: THREE.Vector3;
  preCenter: THREE.Vector3;
  maxDim: number;
  scaleFactor: number;
  postMin: THREE.Vector3;
  postMax: THREE.Vector3;
  postSize: THREE.Vector3;
};

/**
 * Normalize a loaded GLB in place: scale so its largest dimension is
 * ``targetSizeMeters`` (chosen per-object to cover the stock building height),
 * center it horizontally, and rest its base just above y=0 by
 * {@link GROUND_LIFT_METERS} to avoid z-fighting with the map plane.
 */
function normalizeModel(
  model: THREE.Object3D,
  targetSizeMeters: number,
): NormalizeReport {
  model.updateMatrixWorld(true);
  const box = new THREE.Box3().setFromObject(model);
  const size = box.getSize(new THREE.Vector3());
  const preCenter = box.getCenter(new THREE.Vector3());
  const maxDim = Math.max(size.x, size.y, size.z);
  const scaleFactor = maxDim > 0 ? targetSizeMeters / maxDim : 1;
  if (maxDim > 0) {
    model.scale.multiplyScalar(scaleFactor);
  }

  model.updateMatrixWorld(true);
  const scaledBox = new THREE.Box3().setFromObject(model);
  const center = scaledBox.getCenter(new THREE.Vector3());
  model.position.x -= center.x;
  model.position.z -= center.z;
  model.position.y -= scaledBox.min.y;
  model.position.y += GROUND_LIFT_METERS;

  return {
    preMin: box.min.clone(),
    preMax: box.max.clone(),
    preSize: size.clone(),
    preCenter,
    maxDim,
    scaleFactor,
    postMin: scaledBox.min.clone(),
    postMax: scaledBox.max.clone(),
    postSize: scaledBox.getSize(new THREE.Vector3()),
  };
}

/**
 * One-shot, dev-only diagnostics for a freshly loaded model. Dumps the scene
 * hierarchy, per-mesh geometry integrity (vertex/index counts, local bbox,
 * NaN/Infinity checks), the normalize report, and the mercator model matrix, so
 * we can confirm meshes stay in meter space and the transform is applied once.
 */
function logMeshDiagnostics(
  object: MapObjectResponse,
  model: THREE.Object3D,
  report: NormalizeReport,
  modelMatrix: THREE.Matrix4,
  stockHeight: number | null,
  targetSize: number,
): void {
  if (!MESH_DEBUG) {
    return;
  }

  const merc = maplibregl.MercatorCoordinate.fromLngLat([object.lng, object.lat], 0);
  const meterInMercator = merc.meterInMercatorCoordinateUnits();

  /* eslint-disable no-console */
  console.groupCollapsed(`[meshLayer] diagnostics for object ${object.id}`);
  console.log("mesh_url", object.mesh_url);
  console.log("lng/lat", object.lng, object.lat);
  console.log("mercator x/y/z", merc.x, merc.y, merc.z);
  console.log("meterInMercatorCoordinateUnits", meterInMercator);

  console.log("stockBuildingHeight (m, null = fallback)", stockHeight);
  console.log("chosen targetSize (m)", targetSize);
  console.log("normalize.preSize (m)", report.preSize);
  console.log("normalize.preCenter", report.preCenter);
  console.log("normalize.maxDim", report.maxDim);
  console.log("normalize.scaleFactor", report.scaleFactor);
  console.log("normalize.postSize (m, y should cover stock height)", report.postSize);

  let meshCount = 0;
  let totalVerts = 0;
  model.traverse((child) => {
    const mesh = child as THREE.Mesh;
    if (!mesh.isMesh || !mesh.geometry) {
      return;
    }
    meshCount += 1;
    const geometry = mesh.geometry as THREE.BufferGeometry;
    const position = geometry.getAttribute("position") as
      | THREE.BufferAttribute
      | undefined;
    const vertexCount = position?.count ?? 0;
    const indexCount = geometry.getIndex()?.count ?? 0;
    totalVerts += vertexCount;

    geometry.computeBoundingBox();
    const localBox = geometry.boundingBox;

    let hasNonFinite = false;
    if (position) {
      const array = position.array as ArrayLike<number>;
      for (let i = 0; i < array.length; i += 1) {
        if (!Number.isFinite(array[i])) {
          hasNonFinite = true;
          break;
        }
      }
    }
    const zeroSized =
      !localBox || localBox.getSize(new THREE.Vector3()).length() === 0;

    const materialType = Array.isArray(mesh.material)
      ? mesh.material.map((m) => m?.type).join(",")
      : mesh.material?.type;

    console.log(`mesh[${meshCount}] "${mesh.name || "(unnamed)"}"`, {
      vertexCount,
      indexCount,
      materialType,
      localBoxMin: localBox?.min,
      localBoxMax: localBox?.max,
      localPosition: mesh.position.clone(),
      localScale: mesh.scale.clone(),
    });
    if (hasNonFinite) {
      console.warn(`mesh[${meshCount}] has NaN/Infinity in position attribute`);
    }
    if (zeroSized) {
      console.warn(`mesh[${meshCount}] has a zero-sized bounding box`);
    }
  });

  console.log("mesh count", meshCount, "total vertices", totalVerts);
  console.log("modelMatrix (mercator, applied at render)", modelMatrix.elements);
  console.groupEnd();
  /* eslint-enable no-console */
}

/**
 * Recompute vertex normals after the model has been normalized so lighting
 * interacts correctly with the front faces. TRELLIS exports can ship with
 * missing or degenerate normals; recomputing guarantees consistent shading
 * under FrontSide rendering.
 */
function recomputeMeshNormals(root: THREE.Object3D): void {
  root.traverse((child) => {
    const mesh = child as THREE.Mesh;
    if (!mesh.isMesh || !mesh.geometry) {
      return;
    }
    mesh.geometry.computeVertexNormals();
  });
}

/**
 * Harden GLB materials for the shared MapLibre GL context: clamp over-reported
 * metalness and enforce a roughness floor (both make PBR surfaces render black
 * without a full IBL). Rendering stays single-sided (FrontSide) because the
 * anchor transform preserves winding; double-siding here would draw inner faces
 * and cause z-fighting/self-occlusion. Existing textures/maps are preserved.
 */
function prepareMeshMaterials(root: THREE.Object3D): void {
  root.traverse((child) => {
    const mesh = child as THREE.Mesh;
    if (!mesh.isMesh) {
      return;
    }
    const materials = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
    for (const material of materials) {
      if (!material) {
        continue;
      }
      material.side = THREE.FrontSide;
      const standard = material as THREE.MeshStandardMaterial;
      if (typeof standard.metalness === "number") {
        standard.metalness = Math.min(standard.metalness, MAX_METALNESS);
      }
      if (typeof standard.roughness === "number") {
        standard.roughness = Math.max(standard.roughness, MIN_ROUGHNESS);
      }
      material.needsUpdate = true;
    }
  });
}

export class GeneratedMeshLayer implements CustomLayerInterface {
  readonly id = GENERATED_MESHES_LAYER_ID;
  readonly type = "custom" as const;
  readonly renderingMode = "3d" as const;

  private map: MapLibreMap | null = null;
  private renderer: THREE.WebGLRenderer | null = null;
  private envMap: THREE.Texture | null = null;
  private readonly scene = new THREE.Scene();
  private readonly camera = new THREE.Camera();
  private readonly loader = new GLTFLoader();

  private readonly objects = new Map<string, LoadedObject>();
  private readonly loading = new Set<string>();
  private readonly highlightStart = new Map<string, number>();
  /**
   * Live, unsaved heading previews keyed by object id. When present, an
   * override takes precedence over the server heading so a slider drag updates
   * instantly and is not clobbered by background map-state polling until the
   * user saves (which updates {@link desired}) or cancels (which clears it).
   */
  private readonly headingOverrides = new Map<string, number>();
  /**
   * Live, unsaved uniform scale previews keyed by object id, mirroring
   * {@link headingOverrides}. Present while the user drags the scale slider;
   * an override beats the server scale until the user saves or cancels.
   */
  private readonly scaleOverrides = new Map<string, number>();

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
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;

    // Image-based lighting: without an environment map, PBR materials (which
    // TRELLIS exports use) shade near-black and read as a static blob.
    const pmrem = new THREE.PMREMGenerator(this.renderer);
    this.envMap = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
    this.scene.environment = this.envMap;
    pmrem.dispose();

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

    // MapLibre's per-frame view-projection matrix (mercator world -> clip).
    const main = new THREE.Matrix4().fromArray(
      Array.from(options.defaultProjectionData.mainMatrix),
    );

    this.renderer.resetState();

    // Render each object with its own model matrix folded into the projection,
    // matching MapLibre's official three.js example. Meshes stay in meter space
    // in the scene; only this composition maps them to their mercator location,
    // keeping intermediate values large enough for Float32 precision. Lights and
    // the scene environment apply on every pass regardless of which root shows.
    for (const object of this.objects.values()) {
      for (const other of this.objects.values()) {
        other.root.visible = other === object;
      }
      this.camera.projectionMatrix.copy(main).multiply(object.modelMatrix);
      this.renderer.render(this.scene, this.camera);
    }

    for (const object of this.objects.values()) {
      object.root.visible = true;
    }

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
    this.scene.environment = null;
    this.envMap?.dispose();
    this.envMap = null;
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
        this.headingOverrides.delete(id);
        this.scaleOverrides.delete(id);
      }
    }

    for (const object of this.desired) {
      const loaded = this.objects.get(object.id);
      if (loaded) {
        // Already loaded: apply any heading or scale change (from another
        // member's edit arriving via polling, or a local preview override)
        // without reloading the GLB, so the transform stays in sync cheaply.
        this.refreshObjectMatrix(loaded, object);
        continue;
      }
      if (this.loading.has(object.id)) {
        continue;
      }
      this.loadObject(object);
    }
  }

  /** Heading that should be shown for an object: live preview beats server. */
  private effectiveHeading(object: MapObjectResponse): number {
    return this.headingOverrides.get(object.id) ?? object.heading ?? 0;
  }

  /** Scale that should be shown for an object: live preview beats server. */
  private effectiveScale(object: MapObjectResponse): number {
    return this.scaleOverrides.get(object.id) ?? object.scale ?? 1;
  }

  /** Rebuild a loaded object's transform if its heading or scale changed. */
  private refreshObjectMatrix(loaded: LoadedObject, object: MapObjectResponse): void {
    let changed = false;

    const heading = this.effectiveHeading(object);
    if (heading !== loaded.heading) {
      loaded.heading = heading;
      loaded.modelMatrix = anchorMatrix(loaded.lng, loaded.lat, heading);
      changed = true;
    }

    const scale = this.effectiveScale(object);
    if (scale !== loaded.scale) {
      loaded.scale = scale;
      loaded.root.scale.setScalar(scale);
      changed = true;
    }

    if (changed) {
      this.map?.triggerRepaint();
    }
  }

  /**
   * Apply an unsaved heading preview to a placed object and re-render. Used
   * while the user drags the orient slider before saving.
   */
  previewObjectHeading(objectId: string, headingDeg: number): void {
    this.headingOverrides.set(objectId, headingDeg);
    const loaded = this.objects.get(objectId);
    if (loaded) {
      loaded.heading = headingDeg;
      loaded.modelMatrix = anchorMatrix(loaded.lng, loaded.lat, headingDeg);
    }
    this.map?.triggerRepaint();
  }

  /**
   * Apply an unsaved uniform scale preview to a placed object and re-render.
   * Used while the user drags the scale slider before saving. The multiplier is
   * applied to {@link root} on top of the client-side auto-fit.
   */
  previewObjectScale(objectId: string, scale: number): void {
    this.scaleOverrides.set(objectId, scale);
    const loaded = this.objects.get(objectId);
    if (loaded) {
      loaded.scale = scale;
      loaded.root.scale.setScalar(scale);
    }
    this.map?.triggerRepaint();
  }

  /**
   * Drop any unsaved heading preview for an object, snapping it back to the
   * last known server heading from {@link desired}.
   */
  clearHeadingOverride(objectId: string): void {
    if (!this.headingOverrides.delete(objectId)) {
      return;
    }
    const loaded = this.objects.get(objectId);
    const object = this.desired.find((candidate) => candidate.id === objectId);
    if (loaded && object) {
      const heading = object.heading ?? 0;
      loaded.heading = heading;
      loaded.modelMatrix = anchorMatrix(loaded.lng, loaded.lat, heading);
    }
    this.map?.triggerRepaint();
  }

  /**
   * Drop any unsaved scale preview for an object, snapping it back to the last
   * known server scale from {@link desired}.
   */
  clearScaleOverride(objectId: string): void {
    if (!this.scaleOverrides.delete(objectId)) {
      return;
    }
    const loaded = this.objects.get(objectId);
    const object = this.desired.find((candidate) => candidate.id === objectId);
    if (loaded && object) {
      const scale = object.scale ?? 1;
      loaded.scale = scale;
      loaded.root.scale.setScalar(scale);
    }
    this.map?.triggerRepaint();
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

        // Size the mesh to cover the stock building extrusion under the pin. We
        // query the rendered building height and scale so the mesh's vertical
        // extent envelops it; when the height is unknown we fall back to an
        // aggressive fixed size that beats typical low-rise tiles.
        model.updateMatrixWorld(true);
        const preSize = new THREE.Box3()
          .setFromObject(model)
          .getSize(new THREE.Vector3());
        const stockHeight = this.map
          ? queryStockBuildingHeight(this.map, object.lng, object.lat)
          : null;
        const targetSize = targetSizeForStock(preSize, stockHeight);

        const report = normalizeModel(model, targetSize);
        recomputeMeshNormals(model);
        prepareMeshMaterials(model);

        // The mercator anchor is stored, NOT applied to the object. It is
        // composed into the camera projection at render time so the mesh keeps
        // its meter-scale local coordinates (avoids Float32 precision collapse).
        const heading = this.effectiveHeading(object);
        const modelMatrix = anchorMatrix(object.lng, object.lat, heading);
        logMeshDiagnostics(object, model, report, modelMatrix, stockHeight, targetSize);

        const root = new THREE.Object3D();
        root.add(model);
        // Apply the user's uniform scale multiplier on top of the auto-fit
        // (baked into the model's own scale). Kept on the root so live previews
        // and polled edits can rescale without reloading or re-normalizing.
        const scale = this.effectiveScale(object);
        root.scale.setScalar(scale);
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
        this.objects.set(object.id, {
          id: object.id,
          root,
          lng: object.lng,
          lat: object.lat,
          heading,
          scale,
          modelMatrix,
          originalEmissive,
        });
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
