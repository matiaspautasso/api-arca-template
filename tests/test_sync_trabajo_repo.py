from sqlalchemy.orm import Session

from app.repo import SyncTrabajoRepo


def test_al_arrancar_una_consulta_que_quedo_en_curso_se_marca_interrumpida(db_engine):
    with Session(db_engine) as s:
        repo = SyncTrabajoRepo(s)
        repo.iniciar("manual", ["ventas", "compras", "pdfs"])
        repo.actualizar_tipo("ventas", "ok", sincronizados=5)
        repo.actualizar_tipo("compras", "en_curso")

    # El backend se reinició a mitad de la consulta.
    with Session(db_engine) as s:
        SyncTrabajoRepo(s).marcar_interrumpida()

    with Session(db_engine) as s:
        trabajo = SyncTrabajoRepo(s).obtener()
    assert trabajo.estado == "interrumpido"
    assert trabajo.fin is not None
    assert trabajo.tipos["ventas"].estado == "ok"
    assert trabajo.tipos["compras"].estado == "fallo"
    assert trabajo.tipos["compras"].mensaje == "Interrumpida: el backend se reinició."
    assert trabajo.tipos["pdfs"].estado == "fallo"
    # Ya no bloquea una consulta nueva.
    with Session(db_engine) as s:
        assert SyncTrabajoRepo(s).iniciar("manual", ["ventas"]) is True
