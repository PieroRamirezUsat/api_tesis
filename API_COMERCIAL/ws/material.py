from flask import Blueprint, request, jsonify
from models.Material import Material
import json

ws_material = Blueprint("ws_material", __name__, url_prefix="/material")


# ================================
# LISTAR TODO EL MATERIAL
# ================================
@ws_material.route("", methods=["GET"])
def listar_material():
    return jsonify(json.loads(Material.listar()))


# ================================
# CREAR MATERIAL
# ================================
@ws_material.route("", methods=["POST"])
def crear_material():
    data = request.get_json()

    titulo = data.get("titulo")
    descripcion = data.get("descripcion")
    url = data.get("url")
    id_competencia = data.get("id_competencia")

    obj = Material(
        titulo=titulo,
        descripcion=descripcion,
        url=url,
        id_competencia=id_competencia
    )

    return jsonify(json.loads(obj.crear()))


# ================================
# OBTENER MATERIAL POR ID
# ================================
@ws_material.route("/<int:id_material>", methods=["GET"])
def obtener_material(id_material):
    return jsonify(json.loads(Material.obtener(id_material)))


# ================================
# ACTUALIZAR MATERIAL
# ================================
@ws_material.route("/<int:id_material>", methods=["PUT"])
def actualizar_material(id_material):
    data = request.get_json()

    obj = Material(
        id_material=id_material,
        titulo=data.get("titulo"),
        descripcion=data.get("descripcion"),
        url=data.get("url"),
        id_competencia=data.get("id_competencia")
    )

    return jsonify(json.loads(obj.actualizar()))


# ================================
# ELIMINAR MATERIAL
# ================================
@ws_material.route("/<int:id_material>", methods=["DELETE"])
def eliminar_material(id_material):
    return jsonify(json.loads(Material.eliminar(id_material)))
