import datetime
from math import atan2, cos, radians, sin, sqrt
from database import (
    AdminUser,
    Anggota,
    LaporanAbsen,
    PesanSiaran,
    SesiPiket,
    get_db,
)
from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

app = FastAPI(title="JAGUARD PRESISI - Dynamic Geo-Command Center")


def hitung_jarak_km(lat1, lon1, lat2, lon2):
  R = 6371.0
  dlat = radians(lat2 - lat1)
  dlon = radians(lon2 - lon1)
  a = (
      sin(dlat / 2) ** 2
      + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
  )
  c = 2 * atan2(sqrt(a), sqrt(1 - a))
  return R * c


class AdminLoginReq(BaseModel):
  username: str
  password: str
  nama_piket: str
  nama_markas: str
  lat_gps_admin: float
  lng_gps_admin: float
  lat_markas_resmi: float
  lng_markas_resmi: float


class LocationUpdate(BaseModel):
  nrp: str
  latitude: float
  longitude: float
  status_darurat: int = 0


class LaporanKirim(BaseModel):
  nrp: str
  nama: str
  keterangan: str
  foto: str = ""
  latitude: float
  longitude: float


class BalasanAdminReq(BaseModel):
  laporan_id: int
  balasan: str


class SiaranBroadcastReq(BaseModel):
  pesan: str


@app.post("/api/admin/login")
def login_admin(data: AdminLoginReq, db: Session = Depends(get_db)):
  # 1. VALIDASI DOKUMEN/USER ADMIN
  admin = db.query(AdminUser).filter(AdminUser.username == data.username).first()
  if not admin:
    if data.password == "admin123":
      admin = AdminUser(
          username=data.username,
          password=data.password,
          nama_piket=data.nama_piket,
      )
      db.add(admin)
      db.commit()
    else:
      raise HTTPException(
          status_code=401, detail="Username atau Password Admin Salah!"
      )
  elif admin.password != data.password:
    raise HTTPException(
        status_code=401, detail="Username atau Password Admin Salah!"
    )

  # 2. VALIDASI REALISTIS: CEK JARAK GPS ADMIN VS KOORDINAT MARKAS YANG DIINPUT
  if data.lat_gps_admin != 0 and data.lat_markas_resmi != 0:
    jarak_admin_ke_markas = hitung_jarak_km(
        data.lat_gps_admin,
        data.lng_gps_admin,
        data.lat_markas_resmi,
        data.lng_markas_resmi,
    )
    # Batas wilayah hukum operasional admin max 50 KM dari Markas
    if jarak_admin_ke_markas > 50.0:
      raise HTTPException(
          status_code=403,
          detail=(
              f"AKSES DITOLAK: Perangkat Admin berada {int(jarak_admin_ke_markas)} KM"
              f" dari {data.nama_markas}. Tidak sesuai lokasi GPS!"
          ),
      )

  # Nonaktifkan Sesi Piket Sebelumnya
  db.query(SesiPiket).update({"status_aktif": 0})

  # Buat Sesi Piket Baru
  waktu_sekarang = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S WIB")
  sesi_baru = SesiPiket(
      admin_username=data.username,
      nama_markas=data.nama_markas,
      lat_markas=data.lat_markas_resmi,
      lng_markas=data.lng_markas_resmi,
      waktu_mulai=waktu_sekarang,
      status_aktif=1,
  )
  db.add(sesi_baru)
  db.commit()

  return {
      "status": "success",
      "message": "Login Validasi GPS Berhasil",
      "sesi_id": sesi_baru.id,
  }


@app.post("/api/anggota/register")
def register_anggota(
    nrp: str, nama: str, pangkat: str, db: Session = Depends(get_db)
):
  user = db.query(Anggota).filter(Anggota.nrp == nrp).first()
  if user:
    raise HTTPException(status_code=400, detail="NRP sudah terdaftar")
  new_user = Anggota(
      nrp=nrp, nama=nama, pangkat=pangkat, latitude=0.0, longitude=0.0
  )
  db.add(new_user)
  db.commit()
  return {"status": "success", "message": f"Anggota {nama} berhasil terdaftar"}


@app.delete("/api/anggota/hapus/{nrp}")
def hapus_anggota(nrp: str, db: Session = Depends(get_db)):
  user = db.query(Anggota).filter(Anggota.nrp == nrp).first()
  if not user:
    raise HTTPException(status_code=404, detail="Anggota tidak ditemukan")
  db.delete(user)
  db.commit()
  return {"status": "success", "message": "Anggota berhasil dihapus"}


@app.post("/api/location/update")
def update_location(data: LocationUpdate, db: Session = Depends(get_db)):
  user = db.query(Anggota).filter(Anggota.nrp == data.nrp).first()
  if not user:
    raise HTTPException(
        status_code=403,
        detail=(
            "AKSES GAGAL: NRP Anda belum terdaftar oleh Admin Command Center!"
        ),
    )

  sesi_aktif = (
      db.query(SesiPiket)
      .filter(SesiPiket.status_aktif == 1)
      .order_by(SesiPiket.id.desc())
      .first()
  )
  if (
      sesi_aktif
      and sesi_aktif.lat_markas != 0
      and data.latitude != 0
      and data.longitude != 0
  ):
    jarak = hitung_jarak_km(
        sesi_aktif.lat_markas,
        sesi_aktif.lng_markas,
        data.latitude,
        data.longitude,
    )
    if jarak > 50.0:
      raise HTTPException(
          status_code=400,
          detail=(
              f"LOKASI DILUAR JANGKAUAN: Anda berada {int(jarak)} KM dari"
              f" {sesi_aktif.nama_markas}!"
          ),
      )

  user.latitude = data.latitude
  user.longitude = data.longitude
  user.status_darurat = data.status_darurat
  db.commit()
  return {"status": "success", "message": "Lokasi diperbarui"}


@app.post("/api/laporan/kirim")
def kirim_laporan(data: LaporanKirim, db: Session = Depends(get_db)):
  user = db.query(Anggota).filter(Anggota.nrp == data.nrp).first()
  if not user:
    raise HTTPException(
        status_code=403, detail="AKSES GAGAL: NRP Anda belum terdaftar!"
    )

  sesi_aktif = (
      db.query(SesiPiket)
      .filter(SesiPiket.status_aktif == 1)
      .order_by(SesiPiket.id.desc())
      .first()
  )
  sesi_id = sesi_aktif.id if sesi_aktif else 1

  laporan = LaporanAbsen(
      sesi_id=sesi_id,
      nrp=data.nrp,
      nama=data.nama,
      keterangan=data.keterangan,
      foto=data.foto,
      latitude=data.latitude,
      longitude=data.longitude,
      waktu=datetime.datetime.now().strftime("%H:%M:%S WIB"),
  )
  db.add(laporan)
  db.commit()
  return {"status": "success", "message": "Laporan terkirim"}


@app.post("/api/admin/balas")
def balas_laporan(data: BalasanAdminReq, db: Session = Depends(get_db)):
  lap = db.query(LaporanAbsen).filter(LaporanAbsen.id == data.laporan_id).first()
  if not lap:
    raise HTTPException(status_code=404, detail="Laporan tidak ditemukan")
  lap.balasan_admin = data.balasan
  db.commit()
  return {"status": "success", "message": "Balasan terkirim"}


@app.post("/api/admin/broadcast")
def broadcast_siaran(data: SiaranBroadcastReq, db: Session = Depends(get_db)):
  sesi_aktif = (
      db.query(SesiPiket)
      .filter(SesiPiket.status_aktif == 1)
      .order_by(SesiPiket.id.desc())
      .first()
  )
  sesi_id = sesi_aktif.id if sesi_aktif else 1

  siaran = PesanSiaran(
      sesi_id=sesi_id,
      pesan=data.pesan,
      waktu=datetime.datetime.now().strftime("%H:%M:%S WIB"),
      status_aktif=1,
  )
  db.add(siaran)
  db.commit()
  return {"status": "success", "message": "Siaran terkirim"}


@app.get("/api/admin/laporan")
def get_laporan(db: Session = Depends(get_db)):
  sesi_aktif = (
      db.query(SesiPiket)
      .filter(SesiPiket.status_aktif == 1)
      .order_by(SesiPiket.id.desc())
      .first()
  )
  if not sesi_aktif:
    return []
  return (
      db.query(LaporanAbsen)
      .filter(LaporanAbsen.sesi_id == sesi_aktif.id)
      .order_by(LaporanAbsen.id.desc())
      .all()
  )


@app.get("/api/admin/locations")
def get_all_locations(db: Session = Depends(get_db)):
  return db.query(Anggota).all()


@app.get("/api/mobile/sync/{nrp}")
def sync_mobile_data(nrp: str, db: Session = Depends(get_db)):
  sesi_aktif = (
      db.query(SesiPiket)
      .filter(SesiPiket.status_aktif == 1)
      .order_by(SesiPiket.id.desc())
      .first()
  )
  sesi_id = sesi_aktif.id if sesi_aktif else 0

  siaran = (
      db.query(PesanSiaran)
      .filter(PesanSiaran.sesi_id == sesi_id, PesanSiaran.status_aktif == 1)
      .order_by(PesanSiaran.id.desc())
      .first()
  )
  laporan_user = (
      db.query(LaporanAbsen)
      .filter(LaporanAbsen.nrp == nrp, LaporanAbsen.sesi_id == sesi_id)
      .order_by(LaporanAbsen.id.desc())
      .all()
  )
  return {
      "siaran_darurat": (
          {"pesan": siaran.pesan, "waktu": siaran.waktu} if siaran else None
      ),
      "laporan_saya": [
          {
              "id": l.id,
              "keterangan": l.keterangan,
              "waktu": l.waktu,
              "balasan": l.balasan_admin,
          }
          for l in laporan_user
      ],
  }


@app.get("/mobile", response_class=FileResponse)
def mobile_page():
  return "mobile.html"


@app.get("/admin", response_class=FileResponse)
def admin_page():
  return "admin.html"