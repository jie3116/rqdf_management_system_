from flask_wtf import FlaskForm

from wtforms import (
    StringField,
    PasswordField,
    BooleanField,
    SelectField,
    DateField,
    TextAreaField,
    IntegerField,
    FloatField,
    RadioField,
    SubmitField,
)

from wtforms.validators import (
    DataRequired,
    Optional,
    Email,
    Length,
    EqualTo,
)

from app.models import Gender



class LoginForm(FlaskForm):
    # Ini agar bisa menerima input: "admin", "20250001", atau "08123..."
    login_id = StringField('Email / No. HP / NIS', validators=[DataRequired()])

    password = PasswordField('Password', validators=[DataRequired()])
    remember = BooleanField('Ingat Saya')
    submit = SubmitField('Login')


class StudentForm(FlaskForm):
    # Data Siswa
    nis = StringField('NIS', validators=[DataRequired()])
    full_name = StringField('Nama Lengkap Siswa', validators=[DataRequired()])

    # Untuk data email database, tetap WAJIB format email
    email = StringField('Email Siswa (untuk Login)', validators=[DataRequired(), Email()])

    # Pilihan Gender diambil dari Enum di models.py
    gender = SelectField('Jenis Kelamin', choices=[(g.name, g.value) for g in Gender], validators=[DataRequired()])

    class_id = SelectField('Kelas', coerce=int, validators=[DataRequired()])  # Pilihan dinamis diisi di admin.py
    place_of_birth = StringField('Tempat Lahir', validators=[DataRequired()])
    date_of_birth = DateField('Tanggal Lahir', format='%Y-%m-%d', validators=[DataRequired()])
    address = TextAreaField('Alamat Lengkap', validators=[DataRequired()])

    # Data Wali (Otomatis dibuatkan akun)
    parent_name = StringField('Nama Lengkap Wali', validators=[DataRequired()])
    parent_phone = StringField('No WA Wali (untuk Login)', validators=[DataRequired()])
    parent_job = StringField('Pekerjaan Wali', validators=[DataRequired()])

    submit = SubmitField('Simpan Data Siswa')


class ChangePasswordForm(FlaskForm):
    old_password = PasswordField('Password Lama (Saat ini)', validators=[DataRequired()])
    new_password = PasswordField('Password Baru', validators=[
        DataRequired(),
        Length(min=6, message="Password minimal 6 karakter")
    ])
    confirm_password = PasswordField('Konfirmasi Password Baru', validators=[
        DataRequired(),
        EqualTo('new_password', message='Password tidak sama')
    ])
    submit = SubmitField('Simpan Password Baru')


class FeeTypeForm(FlaskForm):
    name = StringField('Nama Biaya (Cth: SPP Juli 2024)', validators=[DataRequired()])
    amount = FloatField('Nominal (Rp)', validators=[DataRequired()])
    academic_year_id = SelectField('Tahun Ajaran', coerce=int, validators=[DataRequired()])
    submit = SubmitField('Simpan Biaya')


class PPDBForm(FlaskForm):
    # === LANGKAH 1: PILIH PROGRAM ===
    program_type = SelectField('Pilihan Program', choices=[
        ('SEKOLAH_BINA_QUR\'AN', 'Sekolah Bina Qur\'an'),
        ('RQDF_SORE', 'Kelas Reguler RQDF'),
        ('TAKHOSUS TAHFIDZ', 'Takhosus Tahfidz')
    ], validators=[DataRequired()])

    scholarship_category = SelectField('Jalur Pendaftaran', choices=[
        ('NON_BEASISWA', 'Non Beasiswa (Reguler)'),
        ('TAHFIDZ_5_JUZ', 'Beasiswa Tahfidz 5 Juz'),
        ('TAHFIDZ_10_30_JUZ', 'Beasiswa Tahfidz 10-30 Juz'),
        ('YATIM_DHUAFA', 'Beasiswa Yatim Dhuafa')
    ], default='NON_BEASISWA')

    # [UPDATE] Tambahkan pilihan SD
    education_level = SelectField('Jenjang Pendidikan', choices=[
        ('SD', 'SD'),
        ('SMP', 'SMP'),
        ('SMA', 'SMA'),
    ], default='SMP')

    # === LANGKAH 2: DATA DIRI ===
    full_name = StringField('Nama Lengkap', validators=[DataRequired()])

    # [UBAH] Jadi Optional agar user SD tidak error saat submit kosong
    nickname = StringField('Nama Panggilan', validators=[Optional()])
    nik = StringField('NIK', validators=[Optional(), Length(max=16)])
    kk_number = StringField('No. KK', validators=[Optional(), Length(max=16)])

    gender = RadioField('Jenis Kelamin', choices=[('L', 'Laki-laki'), ('P', 'Perempuan')], validators=[DataRequired()])
    place_of_birth = StringField('Tempat Lahir', validators=[DataRequired()])
    date_of_birth = DateField('Tanggal Bulan Tahun Lahir', format='%Y-%m-%d', validators=[DataRequired()])

    # [UBAH] Jadi Optional
    age = IntegerField('Usia (Tahun)', validators=[Optional()])

    address = TextAreaField('Alamat Lengkap', validators=[DataRequired()])

    # === LANGKAH 3: SEKOLAH ASAL ===
    # Label disesuaikan permintaan
    previous_school = StringField('Sekolah Asal', validators=[DataRequired()])

    # [UBAH] Jadi Optional
    previous_school_class = StringField('Kelas Terakhir', validators=[Optional()])

    # === LANGKAH 4: DATA ORANG TUA ===
    father_name = StringField('Nama Ayah', validators=[DataRequired()])

    # [UBAH] Jadi Optional (Hidden untuk SD)
    father_job = StringField('Pekerjaan Ayah', validators=[Optional()])
    father_income_range = SelectField('Penghasilan Ayah', choices=[
        ('-', 'Pilih Penghasilan'),
        ('NO_INCOME', 'Tidak ada penghasilan'),
        ('UNDER_5M', 'Di bawah Rp 5.000.000'),
        ('5M_10M', 'Rp 5.000.000 - Rp 10.000.000'),
        ('ABOVE_10M', 'Di atas Rp 10.000.000')
    ], validators=[Optional()])

    mother_name = StringField('Nama Ibu', validators=[DataRequired()])

    # [UBAH] Jadi Optional (Hidden untuk SD)
    mother_job = StringField('Pekerjaan Ibu', validators=[Optional()])
    mother_income_range = SelectField('Penghasilan Ibu', choices=[
        ('-', 'Pilih Penghasilan'),
        ('NO_INCOME', 'Tidak ada penghasilan'),
        ('UNDER_5M', 'Di bawah Rp 5.000.000'),
        ('5M_10M', 'Rp 5.000.000 - Rp 10.000.000'),
        ('ABOVE_10M', 'Di atas Rp 10.000.000')
    ], validators=[Optional()])

    # Label disesuaikan permintaan
    parent_phone = StringField('Nomor Telepon Orang Tua (WhatsApp)', validators=[DataRequired()])

    # === LANGKAH 5: KHUSUS RQDF SORE ===
    tahfidz_schedule = SelectField('Pilihan Jadwal Tahfidz', choices=[
        ('TIDAK_ADA', '-'),
        ('SHIFT_1', '14.00 s.d 15.30'),
        ('SHIFT_2', '16.00 s.d 17.30')
    ], validators=[Optional()])

    uniform_size = SelectField('Ukuran Seragam RQDF', choices=[
        ('TIDAK_MEMILIH', 'Tidak Memilih'),
        ('S', 'Ukuran S (Rp 345.000)'),
        ('M', 'Ukuran M (Rp 345.000)'),
        ('L', 'Ukuran L (Rp 355.000)'),
        ('XL', 'Ukuran XL (Rp 355.000)'),
        ('XXL', 'Ukuran XXL (Rp 380.000)')
    ], validators=[Optional()])

    initial_pledge_amount = SelectField('Infaq Pembangunan Pesantren', choices=[
        ('0', 'Pilih Nominal'),
        ('500000', 'Rp 500.000'),
        ('1000000', 'Rp 1.000.000'),
        ('1500000', 'Rp 1.500.000')
    ], coerce=int, validators=[Optional()])

    # Label disesuaikan permintaan
    finance_agreement = BooleanField(
        'Saya telah membaca dan menyetujui rincian biaya pendidikan di atas',
        validators=[DataRequired(message="Anda harus mencentang YA untuk melanjutkan.")]
    )

    submit = SubmitField('Kirim Pendaftaran')


# Form untuk TU menginput pembayaran
class PaymentForm(FlaskForm):
    amount = FloatField('Jumlah Pembayaran (Rp)', validators=[DataRequired()])
    method = SelectField('Metode Pembayaran', choices=[
        ('TUNAI', 'Tunai / Cash'),
        ('TRANSFER', 'Transfer Bank')
    ], validators=[DataRequired()])
    notes = TextAreaField('Catatan (Opsional)')
    submit = SubmitField('Proses Pembayaran')