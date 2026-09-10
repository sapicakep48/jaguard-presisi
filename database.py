from sqlalchemy import Column, Float, Integer, String, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

DATABASE_URL = "sqlite:///./jaguard.db"

engine = create_engine(
    DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class AdminUser(Base):
  __tablename__ = "admin_user"
  id = Column(Integer, primary_key=True, index=True)
  username = Column(String, unique=True, index=True)
  password = Column(String)
  nama_piket = Column(String)


class SesiPiket(Base):
  __tablename__ = "sesi_piket"
  id = Column(Integer, primary_key=True, index=True)
  admin_username = Column(String)
  nama_markas = Column(String)
  lat_markas = Column(Float, default=0.0)
  lng_markas = Column(Float, default=0.0)
  waktu_mulai = Column(String)
  waktu_selesai = Column(String, default="BERJALAN")
  status_aktif = Column(Integer, default=1)


class Anggota(Base):
  __tablename__ = "anggota"
  id = Column(Integer, primary_key=True, index=True)
  nrp = Column(String, unique=True, index=True)
  nama = Column(String)
  pangkat = Column(String)
  latitude = Column(Float, default=0.0)
  longitude = Column(Float, default=0.0)
  status_darurat = Column(Integer, default=0)


class LaporanAbsen(Base):
  __tablename__ = "laporan_absen"
  id = Column(Integer, primary_key=True, index=True)
  sesi_id = Column(Integer)
  nrp = Column(String)
  nama = Column(String)
  keterangan = Column(String)
  foto = Column(String, default="")
  latitude = Column(Float, default=0.0)
  longitude = Column(Float, default=0.0)
  waktu = Column(String)
  balasan_admin = Column(String, default="")


class PesanSiaran(Base):
  __tablename__ = "pesan_siaran"
  id = Column(Integer, primary_key=True, index=True)
  sesi_id = Column(Integer)
  pesan = Column(String)
  waktu = Column(String)
  status_aktif = Column(Integer, default=1)


Base.metadata.create_all(bind=engine)


def get_db():
  db = SessionLocal()
  try:
    yield db
  finally:
    db.close()