import os, random, string
from datetime import datetime, timedelta
from flask import Flask, render_template, redirect, url_for, request, flash, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_mail import Mail, Message
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from authlib.integrations.flask_client import OAuth
from dotenv import load_dotenv
from models import db, User, Course, Enrollment, Enquiry, Test, Question, TestAttempt, SummerCamp, CampGallery, CampEnquiry, CampActivity, HeroBanner, ActivityPhoto, SiteSettings, CourseVideo, CourseMaterial, Centre, Testimonial, GalleryPhoto, course_centres, CourseCategory, TestRegistration
from functools import wraps

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-prod')

# Database — use PostgreSQL on Render, SQLite locally
database_url = os.getenv('DATABASE_URL', '')
if database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://', 1)
if database_url:
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
else:
    db_dir = os.getenv('DB_DIR', 'instance')
    os.makedirs(db_dir, exist_ok=True)
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.abspath(os.path.join(db_dir, "lms.db"))}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Flask-Mail config — works with Gmail, Brevo, or any SMTP
app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER', 'smtp-relay.brevo.com')
app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME', '')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD', '')
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_USERNAME', 'noreply@ccmc.com')

db.init_app(app)
mail = Mail(app)

# Cloudinary config for image uploads (optional — works without it)
CLOUDINARY_ENABLED = False
try:
    import cloudinary
    import cloudinary.uploader
    if os.getenv('CLOUDINARY_CLOUD_NAME'):
        cloudinary.config(
            cloud_name=os.getenv('CLOUDINARY_CLOUD_NAME', ''),
            api_key=os.getenv('CLOUDINARY_API_KEY', ''),
            api_secret=os.getenv('CLOUDINARY_API_SECRET', '')
        )
        CLOUDINARY_ENABLED = True
except ImportError:
    pass

def upload_image(file):
    if not CLOUDINARY_ENABLED:
        return None
    try:
        result = cloudinary.uploader.upload(file, folder='ccmc', resource_type='image')
        return result.get('secure_url')
    except Exception as e:
        print(f'Upload error: {e}')
        return None

UPLOAD_FOLDER = os.path.join('static', 'uploads', 'aadhaar')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB max for video uploads
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

login_manager = LoginManager(app)
login_manager.login_view = 'login'

oauth = OAuth(app)
google = oauth.register(
    name='google',
    client_id=os.getenv('GOOGLE_CLIENT_ID'),
    client_secret=os.getenv('GOOGLE_CLIENT_SECRET'),
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'}
)

try:
    import razorpay
    rzp = razorpay.Client(auth=(os.getenv('RAZORPAY_KEY_ID', 'rzp_test_demo'),
                                os.getenv('RAZORPAY_KEY_SECRET', 'demo')))
except Exception:
    rzp = None

@login_manager.user_loader
def load_user(uid):
    return User.query.get(int(uid))

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('Admin access required.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def get_settings():
    """Return all site settings as a dict."""
    try:
        settings = SiteSettings.query.all()
        return {s.key: s.value for s in settings}
    except Exception:
        return {}

@app.context_processor
def inject_settings():
    try:
        return {'settings': get_settings()}
    except Exception:
        return {'settings': {}}

# ── Seed ──────────────────────────────────────────────────────────────────────
def seed_courses():
    if Course.query.count() > 0:
        return  # courses already exist — never overwrite admin changes
    courses = [
        # TTP
        dict(title='TTP — Transformation Training Program',
             description='A skill-focused program designed to enhance aptitude, reasoning, and problem-solving abilities for competitive success. Our approach combines concept clarity, regular practice, and performance tracking to build confidence and consistency in every student.',
             category='TTP', sub_category='Aptitude & Reasoning', mode='Offline', duration='3 Months',
             lessons=90, price=0, original_price=0, badge='',
             logo_url='',
             thumbnail='/static/images/WhatsApp Image 2026-03-27 at 2.15.43 PM.jpeg'),
        # TNPSC
        dict(title='TNPSC — Complete Coaching',
             description='Comprehensive coaching for Tamil Nadu Public Service Commission exams with updated syllabus and regular mock tests. Expert guidance, updated study materials, and a focused environment to help learners achieve their goals.',
             category='TNPSC', sub_category='All Groups', mode='Offline/Online', duration='10 Months',
             lessons=250, price=0, original_price=0, badge='',
             logo_url='/static/images/logos/logo_tnpsc.png',
             thumbnail='/static/images/TNPSC.jpg.jpeg'),
        dict(title='TNPSC Group 1 (Prelims cum Mains)',
             description='Complete preparation for TNPSC Group 1 covering General Studies, Tamil, and Aptitude. Includes test series, study material, and mentorship.',
             category='TNPSC', sub_category='Group 1', mode='Offline/Online', duration='10 Months',
             lessons=250, price=0, original_price=0, badge='',
             logo_url='/static/images/logos/logo_tnpsc.png',
             thumbnail='/static/images/TNPSC.jpg.jpeg'),
        dict(title='TNPSC Group 2 / 2A',
             description='Targeted coaching for TNPSC Group 2 and 2A exams with full syllabus coverage, mock tests, and current affairs. Tamil medium support available.',
             category='TNPSC', sub_category='Group 2', mode='Offline/Online', duration='8 Months',
             lessons=200, price=0, original_price=0, badge='',
             logo_url='/static/images/logos/logo_tnpsc.png',
             thumbnail='/static/images/TNPSC.jpg.jpeg'),
        dict(title='TNPSC Group 4 & VAO',
             description='Comprehensive preparation for Group 4 and VAO exams. Covers all topics with Tamil medium support and regular practice tests.',
             category='TNPSC', sub_category='Group 4', mode='Offline/Online', duration='4 Months',
             lessons=100, price=0, original_price=0, badge='',
             logo_url='/static/images/logos/logo_tnpsc.png',
             thumbnail='/static/images/TNPSC.jpg.jpeg'),
        # SSC
        dict(title='SSC — Complete Coaching',
             description='Structured preparation for Staff Selection Commission exams covering quantitative aptitude, reasoning, and general awareness. Our approach combines concept clarity, regular practice, and performance tracking.',
             category='SSC', sub_category='All Exams', mode='Offline/Online', duration='5 Months',
             lessons=200, price=0, original_price=0, badge='',
             logo_url='/static/images/logos/logo_ssc.png',
             thumbnail='/static/images/SSC.png'),
        dict(title='SSC CGL',
             description='End-to-end preparation for SSC CGL Tier I & II. Covers Quantitative Aptitude, English, Reasoning, and General Knowledge with mock tests.',
             category='SSC', sub_category='CGL', mode='Offline/Online', duration='5 Months',
             lessons=200, price=0, original_price=0, badge='',
             logo_url='/static/images/logos/logo_ssc.png',
             thumbnail='/static/images/SSC.png'),
        dict(title='SSC CHSL',
             description='Comprehensive SSC CHSL preparation for Tier I, II, and III with typing test guidance and regular mock tests.',
             category='SSC', sub_category='CHSL', mode='Offline/Online', duration='3 Months',
             lessons=120, price=0, original_price=0, badge='',
             logo_url='/static/images/logos/logo_ssc.png',
             thumbnail='/static/images/SSC.png'),
        # RRB
        dict(title='RRB — Complete Coaching',
             description='Focused training for Railway Recruitment Board exams with exam-oriented strategies and practice sessions. Expert guidance to crack RRB exams in the first attempt.',
             category='RRB', sub_category='All Exams', mode='Offline/Online', duration='4 Months',
             lessons=150, price=0, original_price=0, badge='',
             logo_url='/static/images/logos/logo_rrb.png',
             thumbnail='/static/images/TNPSC.jpg.jpeg'),
        dict(title='RRB NTPC',
             description='Full preparation for RRB NTPC covering Maths, Reasoning, General Awareness, and English. Includes mock tests and previous year paper analysis.',
             category='RRB', sub_category='NTPC', mode='Offline/Online', duration='4 Months',
             lessons=150, price=0, original_price=0, badge='',
             logo_url='/static/images/logos/logo_rrb.png',
             thumbnail='/static/images/RRB.png'),
        dict(title='RRB Group D',
             description='Targeted preparation for RRB Group D exam with complete syllabus coverage, practice sets, and previous year papers.',
             category='RRB', sub_category='Group D', mode='Offline/Online', duration='3 Months',
             lessons=100, price=0, original_price=0, badge='',
             logo_url='/static/images/logos/logo_rrb.png',
             thumbnail='/static/images/RRB.png'),
        # BANKING
        dict(title='Banking — Complete Coaching',
             description='Complete coaching for bank exams including IBPS and SBI, with emphasis on speed, accuracy, and concept mastery. Structured preparation with regular mock tests and performance tracking.',
             category='BANKING', sub_category='All Exams', mode='Offline/Online', duration='4 Months',
             lessons=160, price=0, original_price=0, badge='',
             logo_url='/static/images/logos/logo_banking.png',
             thumbnail='/static/images/UPSC.jpg.jpeg'),
        dict(title='SBI PO & Clerk',
             description='Full preparation for SBI PO and Clerk exams including Reasoning, Quantitative Aptitude, English, General Awareness, and Descriptive Writing.',
             category='BANKING', sub_category='SBI', mode='Offline/Online', duration='4 Months',
             lessons=160, price=0, original_price=0, badge='',
             logo_url='/static/images/logos/logo_banking.png',
             thumbnail='/static/images/UPSC.jpg.jpeg'),
        dict(title='IBPS PO & Clerk',
             description='Comprehensive IBPS PO and Clerk preparation covering all sections with sectional tests, full mock tests, and interview guidance.',
             category='BANKING', sub_category='IBPS', mode='Offline/Online', duration='4 Months',
             lessons=150, price=0, original_price=0, badge='',
             logo_url='/static/images/logos/logo_banking.png',
             thumbnail='/static/images/TNPSC.jpg.jpeg'),
    ]
    for c in courses:
        db.session.add(Course(**c))
    db.session.commit()

# ── Routes ─────────────────────────────────────────────────────────────────────
@app.route('/')
def index():
    featured = Course.query.filter_by(is_active=True).limit(6).all()
    ttp = Course.query.filter_by(category='TTP', is_active=True).all()
    tnpsc = Course.query.filter_by(category='TNPSC', is_active=True).all()
    rrb = Course.query.filter_by(category='RRB', is_active=True).all()
    ssc = Course.query.filter_by(category='SSC', is_active=True).all()
    banking = Course.query.filter_by(category='BANKING', is_active=True).all()
    banners = HeroBanner.query.filter_by(is_active=True).order_by(HeroBanner.order).all()
    centres = Centre.query.filter_by(is_active=True).order_by(Centre.order).all()
    testimonials = Testimonial.query.filter_by(is_active=True).limit(4).all()
    enrolled_ids = [e.course_id for e in current_user.enrollments] if current_user.is_authenticated else []
    my_enrollments = current_user.enrollments if current_user.is_authenticated else []
    ticker_tests = Test.query.filter(
        Test.scheduled_date >= datetime.utcnow().strftime('%Y-%m-%d'),
        Test.is_active == True
    ).order_by(Test.scheduled_date).limit(10).all()
    return render_template('index.html', featured=featured, ttp=ttp, tnpsc=tnpsc,
                           rrb=rrb, ssc=ssc, banking=banking,
                           banners=banners, centres=centres, testimonials=testimonials,
                           enrolled_ids=enrolled_ids, my_enrollments=my_enrollments,
                           ticker_tests=ticker_tests)

@app.route('/courses/<category>')
def courses_by_category(category):
    cat = category.upper()
    courses = Course.query.filter_by(category=cat, is_active=True).all()
    enrolled_ids = [e.course_id for e in current_user.enrollments] if current_user.is_authenticated else []
    centres = Centre.query.filter_by(is_active=True, coming_soon=False).order_by(Centre.order).all()
    return render_template('courses.html', courses=courses, category=cat,
                           enrolled_ids=enrolled_ids, centres=centres,
                           active_location=None)

@app.route('/location/<slug>')
def courses_by_location(slug):
    centre = Centre.query.filter_by(slug=slug, is_active=True).first_or_404()
    courses = [c for c in centre.courses if c.is_active]
    enrolled_ids = [e.course_id for e in current_user.enrollments] if current_user.is_authenticated else []
    centres = Centre.query.filter_by(is_active=True, coming_soon=False).order_by(Centre.order).all()
    return render_template('courses.html', courses=courses, category='All',
                           enrolled_ids=enrolled_ids, centres=centres,
                           active_location=centre)

@app.route('/course/<int:course_id>')
def course_detail(course_id):
    course = Course.query.get_or_404(course_id)
    is_enrolled = False
    if current_user.is_authenticated:
        is_enrolled = Enrollment.query.filter_by(user_id=current_user.id, course_id=course_id).first() is not None
    return render_template('course.html', course=course, is_enrolled=is_enrolled,
                           razorpay_key=os.getenv('RAZORPAY_KEY_ID', 'rzp_test_demo'))

@app.route('/dashboard')
@login_required
def dashboard():
    enrollments = Enrollment.query.filter_by(user_id=current_user.id).all()
    enrolled_course_ids = [e.course_id for e in enrollments]
    # Global tests always show; course tests only if enrolled
    if enrolled_course_ids:
        tests = Test.query.filter(
            db.or_(
                db.and_(Test.course_id.in_(enrolled_course_ids), Test.is_active == True),
                db.and_(Test.course_id == None, Test.is_active == True)
            )
        ).order_by(Test.created_at.desc()).all()
    else:
        # No enrollments — only show global tests
        tests = Test.query.filter_by(course_id=None, is_active=True).order_by(Test.created_at.desc()).all()
    my_attempts = {a.test_id: a for a in TestAttempt.query.filter_by(user_id=current_user.id).all()}
    upcoming_tests = Test.query.filter(
        Test.scheduled_date >= datetime.utcnow().strftime('%Y-%m-%d'),
        Test.is_active == True
    ).order_by(Test.scheduled_date).limit(5).all()
    return render_template('dashboard.html', enrollments=enrollments, tests=tests,
                           my_attempts=my_attempts, upcoming_tests=upcoming_tests)

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        enq = Enquiry(
            name=request.form.get('name',''),
            email=request.form.get('email',''),
            mobile=request.form.get('mobile',''),
            state=request.form.get('state',''),
            city=request.form.get('city',''),
            college=request.form.get('college',''),
            highest_degree=request.form.get('highest_degree',''),
            target_exam=request.form.get('target_exam',''),
            preferred_course=request.form.get('preferred_course',''),
            message=request.form.get('message','')
        )
        db.session.add(enq)
        db.session.commit()
        flash('Enquiry submitted! Our counsellor will contact you shortly.', 'success')
        return redirect(url_for('contact'))
    return render_template('contact.html')

# ── OTP Helpers ───────────────────────────────────────────────────────────────
def generate_otp():
    return ''.join(random.choices(string.digits, k=6))

def send_otp_sms(mobile, otp):
    """Send OTP via Twilio SMS — optional."""
    try:
        account_sid = os.getenv('TWILIO_ACCOUNT_SID')
        auth_token  = os.getenv('TWILIO_AUTH_TOKEN')
        from_number = os.getenv('TWILIO_PHONE_NUMBER')
        if not all([account_sid, auth_token, from_number]):
            return False
        from twilio.rest import Client
        client = Client(account_sid, auth_token)
        client.messages.create(
            body=f'Your CCMC OTP is: {otp}\nValid for 10 minutes. Do not share.',
            from_=from_number,
            to=mobile
        )
        return True
    except Exception as e:
        print(f'SMS error: {e}')
        return False

def send_otp_email(email, name, otp):
    """Send OTP via email."""
    try:
        msg = Message(
            subject='Your CCMC OTP — Verify Your Account',
            recipients=[email]
        )
        msg.html = f"""
        <div style="font-family:Inter,sans-serif;max-width:480px;margin:0 auto;padding:32px;background:#f5f7ff;border-radius:12px;">
          <div style="text-align:center;margin-bottom:24px;">
            <h2 style="color:#1a237e;font-size:24px;margin:0;">🎓 CCMC</h2>
          </div>
          <div style="background:#fff;border-radius:10px;padding:28px;box-shadow:0 4px 20px rgba(0,0,0,0.08);">
            <h3 style="color:#1a1a2e;margin-top:0;">Hi {name},</h3>
            <p style="color:#666;line-height:1.6;">Use the OTP below to verify your account. It expires in <strong>10 minutes</strong>.</p>
            <div style="text-align:center;margin:28px 0;">
              <div style="display:inline-block;background:#1a237e;color:#fff;font-size:36px;font-weight:800;letter-spacing:10px;padding:16px 32px;border-radius:10px;">{otp}</div>
            </div>
            <p style="color:#999;font-size:13px;">If you didn't request this, please ignore this email.</p>
          </div>
          <p style="text-align:center;color:#aaa;font-size:12px;margin-top:16px;">© 2026 CCMC. All rights reserved.</p>
        </div>
        """
        mail.send(msg)
        return True
    except Exception as e:
        print(f'Mail error: {e}')
        return False

# ── Auth ───────────────────────────────────────────────────────────────────────
@app.route('/send-otp', methods=['POST'])
def send_otp():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Invalid request'}), 400
        name     = data.get('name', '').strip()
        email    = data.get('email', '').strip().lower()
        mobile   = data.get('mobile', '').strip()
        password = data.get('password', '')
        aadhaar  = data.get('aadhaar', '').replace(' ', '').strip()
        present_address         = data.get('present_address', '').strip()
        permanent_address       = data.get('permanent_address', '').strip()
        blood_group             = data.get('blood_group', '').strip()
        educational_qualification = data.get('educational_qualification', '').strip()
        dob   = data.get('dob', '').strip()
        phone = data.get('phone', '').strip().replace(' ', '').replace('-', '')

        if not name or not email or not password:
            return jsonify({'error': 'All fields are required.'}), 400
        if not present_address or not permanent_address or not blood_group or not educational_qualification:
            return jsonify({'error': 'Address, blood group and educational qualification are required.'}), 400
        if not dob:
            return jsonify({'error': 'Date of birth is required.'}), 400
        if not phone:
            return jsonify({'error': 'Phone number is required.'}), 400
        # Validate Indian mobile: strip +91 prefix then check 10 digits
        phone_digits = phone.lstrip('+').lstrip('91') if phone.startswith('+91') or phone.startswith('91') else phone
        if not phone_digits.isdigit() or len(phone_digits) != 10:
            return jsonify({'error': 'Enter a valid 10-digit Indian mobile number.'}), 400
        phone_e164 = f'+91{phone_digits}'
        if len(password) < 8:
            return jsonify({'error': 'Password must be at least 8 characters.'}), 400
        if aadhaar and len(aadhaar) != 12:
            return jsonify({'error': 'Aadhaar number must be 12 digits.'}), 400

        masked_aadhaar = f'XXXX-XXXX-{aadhaar[-4:]}' if len(aadhaar) == 12 else ''
        existing = User.query.filter_by(email=email).first()
        otp = generate_otp()
        expires = datetime.utcnow() + timedelta(minutes=10)

        if existing:
            if existing.is_verified:
                return jsonify({'error': 'Email already registered. Please log in.'}), 400
            existing.name = name
            existing.mobile = mobile
            existing.password = generate_password_hash(password)
            existing.aadhaar_number = masked_aadhaar
            existing.present_address = present_address
            existing.permanent_address = permanent_address
            existing.blood_group = blood_group
            existing.educational_qualification = educational_qualification
            existing.dob = dob
            existing.phone = phone_e164
            existing.otp_code = otp
            existing.otp_expires = expires
            db.session.commit()
        else:
            user = User(name=name, email=email, mobile=mobile,
                        password=generate_password_hash(password),
                        aadhaar_number=masked_aadhaar,
                        present_address=present_address,
                        permanent_address=permanent_address,
                        blood_group=blood_group,
                        educational_qualification=educational_qualification,
                        dob=dob, phone=phone_e164,
                        is_verified=False, otp_code=otp, otp_expires=expires)
            db.session.add(user)
            db.session.commit()

        # Send OTP via email + SMS
        mail_sent = send_otp_email(email, name, otp)
        sms_sent  = send_otp_sms(phone_e164, otp)
        if not mail_sent and not sms_sent:
            print(f'\n[DEV] OTP for {email}: {otp}\n')
            return jsonify({'success': True, 'dev': True,
                            'message': f'OTP sent (check server logs): {otp}'})
        return jsonify({'success': True})
    except Exception as e:
        print(f'send-otp error: {e}')
        return jsonify({'error': 'Server error. Please try again.'}), 500

@app.route('/verify-otp', methods=['POST'])
def verify_otp():
    """Step 2: verify OTP and activate account."""
    data = request.get_json()
    email = data.get('email', '').strip().lower()
    otp   = data.get('otp', '').strip()
    user  = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({'error': 'User not found.'}), 404
    if user.is_verified:
        login_user(user)
        return jsonify({'success': True, 'redirect': url_for('index')})
    if not user.otp_code or user.otp_code != otp:
        return jsonify({'error': 'Invalid OTP. Please try again.'}), 400
    if user.otp_expires and datetime.utcnow() > user.otp_expires:
        return jsonify({'error': 'OTP expired. Please request a new one.'}), 400
    user.is_verified = True
    user.otp_code = ''
    user.otp_expires = None
    db.session.commit()
    login_user(user)
    # New user → send to courses page
    return jsonify({'success': True, 'redirect': url_for('index') + '#courses-section', 'new_user': True})

@app.route('/resend-otp', methods=['POST'])
def resend_otp():
    data  = request.get_json()
    email = data.get('email', '').strip().lower()
    user  = User.query.filter_by(email=email).first()
    if not user or user.is_verified:
        return jsonify({'error': 'Invalid request.'}), 400
    otp = generate_otp()
    user.otp_code    = otp
    user.otp_expires = datetime.utcnow() + timedelta(minutes=10)
    db.session.commit()
    mail_sent = send_otp_email(email, user.name, otp)
    sms_sent  = send_otp_sms(user.mobile, otp) if user.mobile else False
    if not mail_sent and not sms_sent:
        print(f'\n[DEV] Resend OTP for {email}: {otp}\n')
        return jsonify({'success': True, 'dev': True, 'message': f'OTP: {otp}'})
    return jsonify({'success': True})

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    return redirect(url_for('index'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        # Accept both form-encoded and JSON
        if request.is_json:
            data = request.get_json()
            email    = data.get('email', '').strip().lower()
            password = data.get('password', '')
        else:
            email    = request.form.get('email', '').strip().lower()
            password = request.form.get('password', '')
        user = User.query.filter_by(email=email).first()
        if not user:
            return jsonify({'error': 'Invalid email or password.'}), 401
        if not user.is_verified:
            return jsonify({'error': 'Account not verified.', 'unverified': True, 'email': email}), 401
        if user.password and check_password_hash(user.password, password):
            login_user(user)
            next_page = request.args.get('next', url_for('index'))
            return jsonify({'success': True, 'redirect': next_page})
        return jsonify({'error': 'Invalid email or password.'}), 401
    return redirect(url_for('index'))

@app.route('/direct-login', methods=['GET', 'POST'])
def direct_login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    error = None
    if request.method == 'POST':
        email = request.form.get('email','').strip().lower()
        password = request.form.get('password','')
        user = User.query.filter_by(email=email).first()
        if user and user.password and check_password_hash(user.password, password):
            user.is_verified = True
            db.session.commit()
            login_user(user)
            return redirect(url_for('index'))
        error = 'Invalid email or password.'
    return render_template('direct_login.html', error=error)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/auth/google')
def google_login():
    redirect_uri = url_for('google_callback', _external=True)
    return google.authorize_redirect(redirect_uri)

@app.route('/auth/google/callback')
def google_callback():
    token = google.authorize_access_token()
    userinfo = token.get('userinfo')
    if not userinfo:
        flash('Google login failed.', 'error')
        return redirect(url_for('index'))
    email = userinfo['email']
    user = User.query.filter_by(email=email).first()

    # BLOCK: New users cannot use Google login — must register with Aadhaar first
    if not user:
        flash('No account found with this Google email. Please register first with your email and Aadhaar details.', 'error')
        return redirect(url_for('index') + '?open=signup')

    # BLOCK: Unverified users (registered but OTP not completed)
    if not user.is_verified:
        flash('Please complete your registration by verifying your OTP first.', 'error')
        return redirect(url_for('index') + '?open=signup')

    # Link Google account if not already linked
    if not user.google_id:
        user.google_id = userinfo['sub']
        user.avatar = userinfo.get('picture', '')
        db.session.commit()

    login_user(user)

    # Existing user with enrollments → dashboard
    if user.enrollments:
        return redirect(url_for('dashboard'))
    # Existing user no enrollments → pick a course
    flash(f'Welcome back, {user.name.split()[0]}! Please select a course to enroll.', 'success')
    return redirect(url_for('index') + '#featured-courses')

# ── Payment ────────────────────────────────────────────────────────────────────
@app.route('/create-order/<int:course_id>', methods=['POST'])
@login_required
def create_order(course_id):
    course = Course.query.get_or_404(course_id)
    # Check already enrolled in THIS course
    if Enrollment.query.filter_by(user_id=current_user.id, course_id=course_id).first():
        return jsonify({'error': 'Already enrolled in this course'}), 400
    # Check already enrolled in ANY course (one course per user)
    existing = Enrollment.query.filter_by(user_id=current_user.id).first()
    if existing:
        return jsonify({'error': f'You are already enrolled in "{existing.course.title}". Only one course enrollment is allowed per account.'}), 400
    try:
        order = rzp.order.create({'amount': course.price, 'currency': 'INR',
                                   'receipt': f'rcpt_{current_user.id}_{course_id}'})
        return jsonify({'order_id': order['id'], 'amount': course.price,
                        'key': os.getenv('RAZORPAY_KEY_ID','rzp_test_demo'),
                        'course_title': course.title})
    except Exception:
        # Demo fallback
        e = Enrollment(user_id=current_user.id, course_id=course_id,
                       payment_id='demo', amount_paid=course.price)
        db.session.add(e)
        db.session.commit()
        return jsonify({'demo': True})

@app.route('/verify-payment', methods=['POST'])
@login_required
def verify_payment():
    data = request.get_json()
    course_id = data.get('course_id')
    course = Course.query.get_or_404(course_id)
    if not Enrollment.query.filter_by(user_id=current_user.id, course_id=course_id).first():
        e = Enrollment(user_id=current_user.id, course_id=course_id,
                       payment_id=data.get('razorpay_payment_id',''), amount_paid=course.price)
        db.session.add(e)
        db.session.commit()
    return jsonify({'success': True})

# ── Admin ──────────────────────────────────────────────────────────────────────
@app.route('/admin')
@login_required
@admin_required
def admin():
    courses = Course.query.order_by(Course.created_at.desc()).all()
    users = User.query.order_by(User.created_at.desc()).all()
    enquiries = Enquiry.query.order_by(Enquiry.created_at.desc()).all()
    total_revenue = db.session.query(db.func.sum(Enrollment.amount_paid)).scalar() or 0
    centres = Centre.query.filter_by(is_active=True).order_by(Centre.order).all()
    categories = CourseCategory.query.filter_by(is_active=True).order_by(CourseCategory.order).all()
    return render_template('admin.html', courses=courses, users=users,
                           enquiries=enquiries, total_revenue=total_revenue // 100,
                           total_enrollments=Enrollment.query.count(),
                           centres=centres, categories=categories)

@app.route('/admin/course/add', methods=['POST'])
@login_required
@admin_required
def admin_add_course():
    try:
        # Handle thumbnail upload
        thumbnail = ''
        if CLOUDINARY_ENABLED and 'thumbnail_file' in request.files and request.files['thumbnail_file'].filename:
            res = cloudinary.uploader.upload(request.files['thumbnail_file'], folder='ccmc/thumbnails')
            thumbnail = res.get('secure_url', '')
        if not thumbnail:
            thumbnail = request.form.get('thumbnail', '')

        # Handle logo upload
        logo_url = ''
        if CLOUDINARY_ENABLED and 'logo_file' in request.files and request.files['logo_file'].filename:
            res = cloudinary.uploader.upload(request.files['logo_file'], folder='ccmc/logos')
            logo_url = res.get('secure_url', '')
        if not logo_url:
            logo_url = request.form.get('logo_url', '')

        course = Course(
            title=request.form.get('title'),
            description=request.form.get('description'),
            category=request.form.get('category', '').upper(),
            sub_category=request.form.get('sub_category', ''),
            mode=request.form.get('mode', 'Online'),
            duration=request.form.get('duration', ''),
            lessons=int(request.form.get('lessons', 0) or 0),
            price=0, original_price=0,
            badge=request.form.get('badge', ''),
            thumbnail=thumbnail,
            logo_url=logo_url,
            youtube_url=request.form.get('youtube_url', '')
        )
        db.session.add(course)
        db.session.flush()  # get course.id

        # Assign locations
        centre_ids = request.form.getlist('centre_ids')
        for cid in centre_ids:
            c = Centre.query.get(int(cid))
            if c:
                course.centres.append(c)

        # Upload videos
        video_titles = request.form.getlist('video_title[]')
        video_files  = request.files.getlist('video_file[]')
        video_urls   = request.form.getlist('video_url[]')
        for i, vtitle in enumerate(video_titles):
            if not vtitle.strip():
                continue
            vurl = ''
            if CLOUDINARY_ENABLED and i < len(video_files) and video_files[i].filename:
                try:
                    res = cloudinary.uploader.upload(video_files[i], folder='ccmc/videos', resource_type='video', chunk_size=6000000)
                    vurl = res.get('secure_url', '')
                except Exception as e:
                    print(f'Video upload error: {e}')
            if not vurl and i < len(video_urls):
                vurl = video_urls[i].strip()
            if vtitle.strip() and vurl:
                db.session.add(CourseVideo(course_id=course.id, title=vtitle.strip(),
                    video_url=vurl, order=i+1))

        # Upload PDFs
        mat_titles = request.form.getlist('mat_title[]')
        mat_files  = request.files.getlist('mat_file[]')
        for i, mtitle in enumerate(mat_titles):
            if not mtitle.strip():
                continue
            if CLOUDINARY_ENABLED and i < len(mat_files) and mat_files[i].filename:
                f = mat_files[i]
                if allowed_material(f.filename):
                    try:
                        res = cloudinary.uploader.upload(f, folder='ccmc/materials', resource_type='raw')
                        furl = res.get('secure_url', '')
                        ftype = f.filename.rsplit('.', 1)[1].lower()
                        db.session.add(CourseMaterial(course_id=course.id, title=mtitle.strip(),
                            file_url=furl, file_type=ftype, order=i+1))
                    except Exception as e:
                        print(f'Material upload error: {e}')

        db.session.commit()
        flash('Course created successfully!', 'success')
    except Exception as ex:
        db.session.rollback()
        flash(f'Error: {ex}', 'error')
    return redirect(url_for('admin'))


@app.route('/admin/course/edit/<int:cid>', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_edit_course(cid):
    course = Course.query.get_or_404(cid)
    centres = Centre.query.filter_by(is_active=True).order_by(Centre.order).all()
    if request.method == 'POST':
        try:
            course.title       = request.form.get('title', course.title)
            course.description = request.form.get('description', course.description)
            course.category    = request.form.get('category', course.category).upper()
            course.sub_category= request.form.get('sub_category', course.sub_category)
            course.mode        = request.form.get('mode', course.mode)
            course.duration    = request.form.get('duration', course.duration)
            course.lessons     = int(request.form.get('lessons', course.lessons) or 0)
            course.badge       = request.form.get('badge', course.badge)
            course.youtube_url = request.form.get('youtube_url', course.youtube_url)

            # Thumbnail
            if CLOUDINARY_ENABLED and 'thumbnail_file' in request.files and request.files['thumbnail_file'].filename:
                res = cloudinary.uploader.upload(request.files['thumbnail_file'], folder='ccmc/thumbnails')
                course.thumbnail = res.get('secure_url', course.thumbnail)
            elif request.form.get('thumbnail'):
                course.thumbnail = request.form.get('thumbnail')

            # Logo
            if CLOUDINARY_ENABLED and 'logo_file' in request.files and request.files['logo_file'].filename:
                res = cloudinary.uploader.upload(request.files['logo_file'], folder='ccmc/logos')
                course.logo_url = res.get('secure_url', course.logo_url)
            elif request.form.get('logo_url'):
                course.logo_url = request.form.get('logo_url')

            # Locations — use raw SQL for reliability on PostgreSQL
            try:
                course.centres.clear()
                db.session.flush()
                for cid_str in request.form.getlist('centre_ids'):
                    c = Centre.query.get(int(cid_str))
                    if c and c not in course.centres:
                        course.centres.append(c)
            except Exception as loc_err:
                print(f'Location update error: {loc_err}')
                db.session.rollback()
                # Retry with raw SQL
                db.session.execute(db.text('DELETE FROM course_centres WHERE course_id = :cid'), {'cid': course.id})
                for cid_str in request.form.getlist('centre_ids'):
                    db.session.execute(db.text('INSERT INTO course_centres (course_id, centre_id) VALUES (:cid, :lid) ON CONFLICT DO NOTHING'),
                                       {'cid': course.id, 'lid': int(cid_str)})

            # New videos
            video_titles = request.form.getlist('video_title[]')
            video_files  = request.files.getlist('video_file[]')
            video_urls   = request.form.getlist('video_url[]')
            for i, vtitle in enumerate(video_titles):
                if not vtitle.strip():
                    continue
                vurl = ''
                if CLOUDINARY_ENABLED and i < len(video_files) and video_files[i].filename:
                    try:
                        res = cloudinary.uploader.upload(video_files[i], folder='ccmc/videos', resource_type='video', chunk_size=6000000)
                        vurl = res.get('secure_url', '')
                    except Exception as e:
                        print(f'Video upload error: {e}')
                if not vurl and i < len(video_urls):
                    vurl = video_urls[i].strip()
                if vtitle.strip() and vurl:
                    db.session.add(CourseVideo(course_id=course.id, title=vtitle.strip(),
                        video_url=vurl, order=CourseVideo.query.filter_by(course_id=course.id).count()+1))

            # New PDFs
            mat_titles = request.form.getlist('mat_title[]')
            mat_files  = request.files.getlist('mat_file[]')
            for i, mtitle in enumerate(mat_titles):
                if not mtitle.strip():
                    continue
                if CLOUDINARY_ENABLED and i < len(mat_files) and mat_files[i].filename:
                    f = mat_files[i]
                    if allowed_material(f.filename):
                        try:
                            res = cloudinary.uploader.upload(f, folder='ccmc/materials', resource_type='raw')
                            db.session.add(CourseMaterial(course_id=course.id, title=mtitle.strip(),
                                file_url=res.get('secure_url',''), file_type=f.filename.rsplit('.',1)[1].lower(),
                                order=CourseMaterial.query.filter_by(course_id=course.id).count()+1))
                        except Exception as e:
                            print(f'Material upload error: {e}')

            db.session.commit()
            flash('Course updated!', 'success')
        except Exception as ex:
            db.session.rollback()
            flash(f'Error saving course: {ex}', 'error')
            print(f'admin_edit_course error: {ex}')
        return redirect(url_for('admin_edit_course', cid=course.id))

    videos    = CourseVideo.query.filter_by(course_id=cid).order_by(CourseVideo.order).all()
    materials = CourseMaterial.query.filter_by(course_id=cid).order_by(CourseMaterial.order).all()
    selected_centre_ids = [c.id for c in course.centres]
    categories = CourseCategory.query.filter_by(is_active=True).order_by(CourseCategory.order).all()
    return render_template('admin_edit_course.html', course=course, centres=centres,
                           videos=videos, materials=materials, selected_centre_ids=selected_centre_ids,
                           categories=categories)



@app.route('/admin/course/delete/<int:cid>', methods=['POST'])
@login_required
@admin_required
def admin_delete_course(cid):
    db.session.delete(Course.query.get_or_404(cid))
    db.session.commit()
    flash('Course deleted.', 'success')
    return redirect(url_for('admin'))

@app.route('/admin/enquiry/delete/<int:eid>', methods=['POST'])
@login_required
@admin_required
def admin_delete_enquiry(eid):
    db.session.delete(Enquiry.query.get_or_404(eid))
    db.session.commit()
    return redirect(url_for('admin'))

# ── Category Management ────────────────────────────────────────────────────────
@app.route('/admin/category/add', methods=['POST'])
@login_required
@admin_required
def admin_add_category():
    name  = request.form.get('name', '').strip().upper()
    label = request.form.get('label', '').strip() or name
    if not name:
        flash('Category name is required.', 'error')
        return redirect(url_for('admin'))
    if CourseCategory.query.filter_by(name=name).first():
        flash(f'Category "{name}" already exists.', 'error')
        return redirect(url_for('admin'))
    order = CourseCategory.query.count() + 1
    db.session.add(CourseCategory(name=name, label=label, order=order))
    db.session.commit()
    flash(f'Category "{name}" added!', 'success')
    return redirect(url_for('admin'))

@app.route('/admin/category/delete/<int:cid>', methods=['POST'])
@login_required
@admin_required
def admin_delete_category(cid):
    db.session.delete(CourseCategory.query.get_or_404(cid))
    db.session.commit()
    flash('Category deleted.', 'success')
    return redirect(url_for('admin'))

# ── Location (Centre) Management ───────────────────────────────────────────────
@app.route('/admin/location/add', methods=['POST'])
@login_required
@admin_required
def admin_add_location():
    name    = request.form.get('name', '').strip()
    address = request.form.get('address', '').strip()
    desc    = request.form.get('description', '').strip()
    coming  = request.form.get('coming_soon') == 'on'
    if not name:
        flash('Location name is required.', 'error')
        return redirect(url_for('admin'))
    slug = name.lower().replace(' ', '-').replace('/', '-')
    if Centre.query.filter_by(slug=slug).first():
        flash(f'Location "{name}" already exists.', 'error')
        return redirect(url_for('admin'))
    order = Centre.query.count() + 1
    db.session.add(Centre(name=name, slug=slug, address=address,
                          description=desc, order=order,
                          is_active=True, coming_soon=coming))
    db.session.commit()
    flash(f'Location "{name}" added!', 'success')
    return redirect(url_for('admin'))

@app.route('/admin/location/delete/<int:lid>', methods=['POST'])
@login_required
@admin_required
def admin_delete_location(lid):
    db.session.delete(Centre.query.get_or_404(lid))
    db.session.commit()
    flash('Location deleted.', 'success')
    return redirect(url_for('admin') + '#locations')

@app.route('/admin/location/edit/<int:lid>', methods=['POST'])
@login_required
@admin_required
def admin_edit_location(lid):
    loc = Centre.query.get_or_404(lid)
    loc.name        = request.form.get('name', loc.name).strip()
    loc.address     = request.form.get('address', loc.address).strip()
    loc.description = request.form.get('description', loc.description).strip()
    loc.coming_soon = request.form.get('coming_soon') == 'on'
    # regenerate slug only if name changed
    new_slug = loc.name.lower().replace(' ', '-').replace('/', '-')
    if not Centre.query.filter(Centre.slug == new_slug, Centre.id != lid).first():
        loc.slug = new_slug
    db.session.commit()
    flash(f'Location "{loc.name}" updated.', 'success')
    return redirect(url_for('admin') + '#locations')

# ── Test Admin Routes ──────────────────────────────────────────────────────────
@app.route('/admin/test/create', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_create_test():
    courses = Course.query.filter_by(is_active=True).all()
    if request.method == 'POST':
        course_id_raw = request.form.get('course_id', '').strip()
        test = Test(
            course_id=int(course_id_raw) if course_id_raw else None,
            title=request.form.get('title'),
            description=request.form.get('description', ''),
            duration_mins=int(request.form.get('duration_mins', 30)),
            scheduled_date=request.form.get('scheduled_date', ''),
            scheduled_time=request.form.get('scheduled_time', '10:00')
        )
        db.session.add(test)
        db.session.flush()
        texts = request.form.getlist('q_text[]')
        a_opts = request.form.getlist('q_a[]')
        b_opts = request.form.getlist('q_b[]')
        c_opts = request.form.getlist('q_c[]')
        d_opts = request.form.getlist('q_d[]')
        corrects = request.form.getlist('q_correct[]')
        marks_list = request.form.getlist('q_marks[]')
        for i, text in enumerate(texts):
            if text.strip():
                q = Question(
                    test_id=test.id, text=text.strip(),
                    option_a=a_opts[i], option_b=b_opts[i],
                    option_c=c_opts[i], option_d=d_opts[i],
                    correct=corrects[i].upper(),
                    marks=int(marks_list[i]) if marks_list[i] else 1
                )
                db.session.add(q)
        db.session.commit()
        flash(f'Test "{test.title}" created with {len([t for t in texts if t.strip()])} questions!', 'success')
        return redirect(url_for('admin_tests'))
    return render_template('admin_create_test.html', courses=courses)

@app.route('/admin/tests')
@login_required
@admin_required
def admin_tests():
    tests = Test.query.order_by(Test.created_at.desc()).all()
    return render_template('admin_tests.html', tests=tests, now=datetime.utcnow())

# ── Calendar & Test Registration ───────────────────────────────────────────────
@app.route('/exam-calendar')
def exam_calendar():
    # All scheduled tests
    tests = Test.query.filter(Test.scheduled_date != '', Test.is_active == True)\
                      .order_by(Test.scheduled_date).all()
    # Build a dict: date_str -> list of tests
    calendar_data = {}
    for t in tests:
        calendar_data.setdefault(t.scheduled_date, []).append(t)
    upcoming = [t for t in tests if t.scheduled_date >= datetime.utcnow().strftime('%Y-%m-%d')][:5]
    return render_template('exam_calendar.html', tests=tests,
                           calendar_data=calendar_data, upcoming=upcoming)

@app.route('/test/<int:test_id>/register', methods=['GET', 'POST'])
def test_register_view(test_id):
    test = Test.query.get_or_404(test_id)
    if request.method == 'POST':
        name  = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        phone = request.form.get('phone', '').strip()
        if not name or not email:
            flash('Name and email are required.', 'error')
            return redirect(url_for('test_register_view', test_id=test_id))
        # Check duplicate
        existing = TestRegistration.query.filter_by(test_id=test_id, email=email).first()
        if not existing:
            uid = current_user.id if current_user.is_authenticated else None
            db.session.add(TestRegistration(test_id=test_id, user_id=uid,
                                            name=name, email=email, phone=phone))
            db.session.commit()
            # Send reminder email
            try:
                msg = Message(
                    subject=f'Registered: {test.title} — CCMC',
                    recipients=[email]
                )
                msg.html = f"""
                <div style="font-family:Inter,sans-serif;max-width:480px;margin:0 auto;padding:32px;background:#f5f7ff;border-radius:12px;">
                  <h2 style="color:#1a237e;">🎓 CCMC Exam Registration</h2>
                  <p>Hi <strong>{name}</strong>,</p>
                  <p>You have successfully registered for:</p>
                  <div style="background:#fff;border-radius:10px;padding:20px;margin:16px 0;">
                    <h3 style="color:#1a237e;margin:0 0 8px;">{test.title}</h3>
                    <p style="margin:4px 0;">📅 Date: <strong>{test.scheduled_date}</strong></p>
                    <p style="margin:4px 0;">⏰ Time: <strong>{test.scheduled_time}</strong></p>
                    <p style="margin:4px 0;">⏱ Duration: <strong>{test.duration_mins} minutes</strong></p>
                  </div>
                  <p style="color:#666;">To attempt this exam, you need to <a href="https://ccmc.onrender.com">create a free account</a> and enroll in the course.</p>
                  <p style="color:#aaa;font-size:12px;">© 2026 CCMC. All rights reserved.</p>
                </div>
                """
                mail.send(msg)
            except Exception as e:
                print(f'Registration email error: {e}')
        flash(f'Successfully registered for {test.title}! Check your email for details.', 'success')
        return redirect(url_for('exam_calendar'))
    registered = False
    if current_user.is_authenticated:
        registered = TestRegistration.query.filter_by(test_id=test_id, user_id=current_user.id).first() is not None
    return render_template('exam_calendar.html', single_test=test, registered=registered,
                           tests=[], calendar_data={}, upcoming=[])

@app.route('/admin/test/<int:test_id>/leaderboard')
@login_required
@admin_required
def admin_leaderboard(test_id):
    test = Test.query.get_or_404(test_id)
    attempts = (TestAttempt.query
                .filter_by(test_id=test_id)
                .order_by(TestAttempt.score.desc(), TestAttempt.time_taken.asc())
                .all())
    return render_template('leaderboard.html', test=test, attempts=attempts, is_admin=True)

@app.route('/admin/test/<int:test_id>/report')
@login_required
@admin_required
def admin_test_report(test_id):
    test = Test.query.get_or_404(test_id)
    attempts = (TestAttempt.query
                .filter_by(test_id=test_id)
                .order_by(TestAttempt.score.desc(), TestAttempt.time_taken.asc())
                .all())
    return render_template('admin_test_report.html', test=test, attempts=attempts, now=datetime.utcnow())

@app.route('/admin/test/delete/<int:test_id>', methods=['POST'])
@login_required
@admin_required
def admin_delete_test(test_id):
    db.session.delete(Test.query.get_or_404(test_id))
    db.session.commit()
    flash('Test deleted.', 'success')
    return redirect(url_for('admin_tests'))

@app.route('/admin/test/edit/<int:test_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_edit_test(test_id):
    test = Test.query.get_or_404(test_id)
    today = datetime.utcnow().strftime('%Y-%m-%d')
    # Block editing finished tests (has attempts AND date is past)
    is_finished = bool(test.attempts) and bool(test.scheduled_date) and test.scheduled_date < today
    if is_finished:
        flash('Cannot edit a finished test that already has attempts.', 'error')
        return redirect(url_for('admin_tests'))
    courses = Course.query.filter_by(is_active=True).all()
    if request.method == 'POST':
        test.title         = request.form.get('title', test.title).strip()
        test.description   = request.form.get('description', test.description).strip()
        test.duration_mins = int(request.form.get('duration_mins', test.duration_mins) or 30)
        test.scheduled_date = request.form.get('scheduled_date', test.scheduled_date).strip()
        test.scheduled_time = request.form.get('scheduled_time', test.scheduled_time).strip()
        course_id_raw = request.form.get('course_id', '').strip()
        test.course_id = int(course_id_raw) if course_id_raw else None
        db.session.commit()
        flash(f'Test "{test.title}" updated!', 'success')
        return redirect(url_for('admin_tests'))
    return render_template('admin_edit_test.html', test=test, courses=courses)

# ── Student Test Routes ────────────────────────────────────────────────────────
@app.route('/test/<int:test_id>')
@login_required
def take_test(test_id):
    test = Test.query.get_or_404(test_id)
    if not test.is_global:
        enrolled = Enrollment.query.filter_by(user_id=current_user.id, course_id=test.course_id).first()
        if not enrolled:
            flash('You must enroll in the course to take this test.', 'error')
            return redirect(url_for('course_detail', course_id=test.course_id))
    already = TestAttempt.query.filter_by(test_id=test_id, user_id=current_user.id).first()
    if already:
        # Check 1-week retake lock
        if already.retake_after and datetime.utcnow() < already.retake_after:
            days_left = (already.retake_after - datetime.utcnow()).days + 1
            flash(f'You can retake this test after {days_left} day(s).', 'error')
            return redirect(url_for('test_result', test_id=test_id))
        # Allow retake — delete old attempt
        db.session.delete(already)
        db.session.commit()
    return render_template('take_test.html', test=test)

@app.route('/test/<int:test_id>/submit', methods=['POST'])
@login_required
def submit_test(test_id):
    test = Test.query.get_or_404(test_id)
    if TestAttempt.query.filter_by(test_id=test_id, user_id=current_user.id).first():
        return jsonify({'error': 'Already submitted'}), 400
    data = request.get_json()
    answers = data.get('answers', {})  # {question_id: 'A'/'B'/'C'/'D'}
    time_taken = data.get('time_taken', 0)
    score = 0
    correct_count = 0
    wrong_count = 0
    total_marks = sum(q.marks for q in test.questions)
    for q in test.questions:
        ans = answers.get(str(q.id), '').upper()
        if ans == q.correct:
            score += q.marks
            correct_count += 1
        elif ans:
            wrong_count += 1
    attempt = TestAttempt(
        test_id=test_id, user_id=current_user.id,
        score=score, total_marks=total_marks,
        correct_count=correct_count, wrong_count=wrong_count,
        time_taken=time_taken,
        retake_after=datetime.utcnow() + timedelta(weeks=1)
    )
    db.session.add(attempt)
    db.session.commit()
    return jsonify({'success': True, 'score': score, 'total': total_marks})

@app.route('/test/<int:test_id>/result')
@login_required
def test_result(test_id):
    test = Test.query.get_or_404(test_id)
    attempt = TestAttempt.query.filter_by(test_id=test_id, user_id=current_user.id).first_or_404()
    rank = (TestAttempt.query
            .filter_by(test_id=test_id)
            .filter(TestAttempt.score > attempt.score).count()) + 1
    total_attempts = TestAttempt.query.filter_by(test_id=test_id).count()
    return render_template('test_result.html', test=test, attempt=attempt, rank=rank, total_attempts=total_attempts)

@app.route('/test/<int:test_id>/leaderboard')
@login_required
def test_leaderboard(test_id):
    test = Test.query.get_or_404(test_id)
    if not test.is_global:
        enrolled = Enrollment.query.filter_by(user_id=current_user.id, course_id=test.course_id).first()
        if not enrolled:
            flash('Enroll in the course to view leaderboard.', 'error')
            return redirect(url_for('index'))
    attempts = (TestAttempt.query.filter_by(test_id=test_id)
                .order_by(TestAttempt.score.desc(), TestAttempt.time_taken.asc()).all())
    my_attempt = TestAttempt.query.filter_by(test_id=test_id, user_id=current_user.id).first()
    return render_template('leaderboard.html', test=test, attempts=attempts, is_admin=False, my_attempt=my_attempt)

# ── Demo Test Seed ─────────────────────────────────────────────────────────────
def seed_demo_test():
    if Test.query.filter_by(title='General Aptitude Test — Demo').first():
        return
    test = Test(
        course_id=None,  # Global — visible to all students
        title='General Aptitude Test — Demo',
        description='A 25-question aptitude test covering Reasoning, Quantitative Aptitude, and General Knowledge. Open to all registered students.',
        duration_mins=10,
        is_active=True
    )
    db.session.add(test)
    db.session.flush()

    questions = [
        # Reasoning (Q1–8)
        ('If A is the brother of B, B is the sister of C, then A is the __ of C.', 'Sister', 'Brother', 'Father', 'Mother', 'B'),
        ('Find the odd one out: Apple, Mango, Potato, Banana', 'Apple', 'Mango', 'Potato', 'Banana', 'C'),
        ('Complete the series: 2, 4, 8, 16, __', '24', '32', '28', '30', 'B'),
        ('If BOOK is coded as CPPL, how is DESK coded?', 'EFLT', 'EFTL', 'DFTL', 'EFTK', 'B'),
        ('A is taller than B. C is taller than A. Who is the tallest?', 'A', 'B', 'C', 'Cannot determine', 'C'),
        ('Find the missing number: 3, 6, 11, 18, 27, __', '36', '38', '40', '38', 'B'),
        ('If 6 × 4 = 46, 5 × 3 = 35, then 7 × 5 = ?', '57', '75', '35', '12', 'A'),
        ('Which direction is opposite to North-East?', 'South-West', 'North-West', 'South-East', 'West', 'A'),
        # Quantitative Aptitude (Q9–17)
        ('What is 15% of 200?', '25', '30', '35', '20', 'B'),
        ('A train travels 60 km in 1 hour. How far will it travel in 2.5 hours?', '120 km', '150 km', '180 km', '100 km', 'B'),
        ('If the price of an item is ₹500 and it is sold at 20% discount, what is the selling price?', '₹400', '₹450', '₹380', '₹420', 'A'),
        ('What is the simple interest on ₹1000 at 5% per annum for 2 years?', '₹50', '₹100', '₹150', '₹200', 'B'),
        ('The average of 5 numbers is 20. If one number is removed, the average becomes 18. What is the removed number?', '24', '26', '28', '30', 'C'),
        ('A can do a work in 10 days, B in 15 days. Together they finish in?', '5 days', '6 days', '8 days', '12 days', 'B'),
        ('What is the square root of 144?', '11', '12', '13', '14', 'B'),
        ('If 3x + 7 = 22, what is x?', '3', '4', '5', '6', 'C'),
        ('A shopkeeper buys goods for ₹800 and sells for ₹1000. Profit %?', '20%', '25%', '15%', '30%', 'B'),
        # General Knowledge (Q18–25)
        ('Who is the President of India as of 2024?', 'Ram Nath Kovind', 'Droupadi Murmu', 'Pranab Mukherjee', 'A.P.J. Abdul Kalam', 'B'),
        ('Which city is known as the Manchester of South India?', 'Chennai', 'Bengaluru', 'Coimbatore', 'Madurai', 'C'),
        ('UPSC stands for?', 'Union Public Service Commission', 'United Public Service Council', 'Union Police Service Commission', 'United Police Service Council', 'A'),
        ('Which is the longest river in India?', 'Yamuna', 'Godavari', 'Ganga', 'Brahmaputra', 'C'),
        ('TNPSC conducts exams for which state?', 'Telangana', 'Tamil Nadu', 'Tripura', 'Uttarakhand', 'B'),
        ('What is the capital of Tamil Nadu?', 'Coimbatore', 'Madurai', 'Chennai', 'Salem', 'C'),
        ('RRB stands for?', 'Railway Recruitment Board', 'Road Recruitment Bureau', 'Railway Registration Board', 'Rural Recruitment Board', 'A'),
        ('SSC CGL exam is conducted by?', 'UPSC', 'State Government', 'Staff Selection Commission', 'Railway Board', 'C'),
    ]

    for q in questions:
        text, a, b, c, d, correct = q
        db.session.add(Question(
            test_id=test.id, text=text,
            option_a=a, option_b=b, option_c=c, option_d=d,
            correct=correct, marks=1
        ))

    db.session.commit()
    print('Demo aptitude test seeded.')

def seed_scheduled_tests():
    """Seed 5 demo scheduled tests on upcoming Saturdays."""
    if Test.query.filter(Test.scheduled_date != '').count() >= 5:
        return
    # Find next 5 Saturdays from today
    from datetime import date, timedelta
    today = date.today()
    days_until_sat = (5 - today.weekday()) % 7
    if days_until_sat == 0:
        days_until_sat = 7
    saturdays = [(today + timedelta(weeks=i, days=days_until_sat)) for i in range(5)]

    demos = [
        ('TNPSC Group 2 — Mock Test 1', 'TNPSC', 'Full syllabus mock test covering History, Polity, Geography and Current Affairs.'),
        ('SSC CGL — Mock Test 1',       'SSC',   'Quantitative Aptitude, Reasoning, English and General Awareness.'),
        ('RRB NTPC — Mock Test 1',      'RRB',   'Mathematics, General Intelligence & Reasoning, General Awareness.'),
        ('Banking (IBPS PO) — Mock Test 1', 'BANKING', 'Reasoning, Quantitative Aptitude, English Language, General Awareness.'),
        ('TNPSC Group 4 — Mock Test 1', 'TNPSC', 'General Studies and General Tamil — full length mock test.'),
    ]
    for i, (title, cat, desc) in enumerate(demos):
        if Test.query.filter_by(title=title).first():
            continue
        course = Course.query.filter_by(category=cat, is_active=True).first()
        t = Test(
            course_id=course.id if course else None,
            title=title,
            description=desc,
            duration_mins=90,
            scheduled_date=saturdays[i].strftime('%Y-%m-%d'),
            scheduled_time='10:00',
            is_active=True
        )
        db.session.add(t)
    db.session.commit()
    print('Scheduled demo tests seeded.')

# ── Startup: runs under both Gunicorn and python app.py ───────────────────────
def init_db():
    with app.app_context():
        db.create_all()
        # Add missing columns for existing DBs (safe migration)
        # Create ALL tables including new ones added after initial deploy
        db.create_all()
        try:
            with db.engine.connect() as conn:
                is_postgres = 'postgresql' in str(db.engine.url)
                # ALTER TABLE with IF NOT EXISTS only works on PostgreSQL
                # On SQLite we catch the duplicate column error silently
                alter_sqls = [
                    # ── user columns ──────────────────────────────────────────
                    'ALTER TABLE "user" ADD COLUMN aadhaar_number VARCHAR(14) DEFAULT \'\'',
                    'ALTER TABLE "user" ADD COLUMN aadhaar_doc VARCHAR(300) DEFAULT \'\'',
                    'ALTER TABLE "user" ADD COLUMN aadhaar_status VARCHAR(20) DEFAULT \'none\'',
                    'ALTER TABLE "user" ADD COLUMN aadhaar_remark VARCHAR(200) DEFAULT \'\'',
                    'ALTER TABLE "user" ADD COLUMN present_address TEXT DEFAULT \'\'',
                    'ALTER TABLE "user" ADD COLUMN permanent_address TEXT DEFAULT \'\'',
                    'ALTER TABLE "user" ADD COLUMN blood_group VARCHAR(10) DEFAULT \'\'',
                    'ALTER TABLE "user" ADD COLUMN educational_qualification VARCHAR(200) DEFAULT \'\'',
                    'ALTER TABLE "user" ADD COLUMN dob VARCHAR(20) DEFAULT \'\'',
                    'ALTER TABLE "user" ADD COLUMN phone VARCHAR(15) DEFAULT \'\'',
                    # ── course columns ────────────────────────────────────────
                    'ALTER TABLE course ADD COLUMN youtube_url VARCHAR(300) DEFAULT \'\'',
                    'ALTER TABLE course ADD COLUMN logo_url VARCHAR(300) DEFAULT \'\'',
                    'ALTER TABLE course ADD COLUMN mode VARCHAR(40) DEFAULT \'Online\'',
                    'ALTER TABLE course ADD COLUMN sub_category VARCHAR(80) DEFAULT \'\'',
                    'ALTER TABLE course ADD COLUMN badge VARCHAR(60) DEFAULT \'\'',
                    'ALTER TABLE course ADD COLUMN thumbnail VARCHAR(300) DEFAULT \'\'',
                    # ── centre columns ────────────────────────────────────────
                    'ALTER TABLE centre ADD COLUMN coming_soon BOOLEAN DEFAULT FALSE',
                    'ALTER TABLE centre ADD COLUMN image_url VARCHAR(300) DEFAULT \'\'',
                    # ── test_attempt columns ──────────────────────────────────
                    'ALTER TABLE test_attempt ADD COLUMN retake_after TIMESTAMP',
                    'ALTER TABLE test ADD COLUMN scheduled_date VARCHAR(20) DEFAULT \'\'',
                    'ALTER TABLE test ADD COLUMN scheduled_time VARCHAR(10) DEFAULT \'10:00\'',
                ]
                # PostgreSQL: use IF NOT EXISTS syntax
                if is_postgres:
                    alter_sqls = [s.replace('ADD COLUMN ', 'ADD COLUMN IF NOT EXISTS ') for s in alter_sqls]
                for sql in alter_sqls:
                    try:
                        conn.execute(db.text(sql))
                    except Exception:
                        pass  # column already exists — safe to ignore

                # course_centres many-to-many — db.create_all() handles this
                # but add explicit fallback for older deploys
                if is_postgres:
                    try:
                        conn.execute(db.text(
                            'CREATE TABLE IF NOT EXISTS course_centres '
                            '(course_id INTEGER NOT NULL, centre_id INTEGER NOT NULL, '
                            'PRIMARY KEY (course_id, centre_id), '
                            'FOREIGN KEY(course_id) REFERENCES course(id), '
                            'FOREIGN KEY(centre_id) REFERENCES centre(id))'
                        ))
                        conn.execute(db.text(
                            'CREATE TABLE IF NOT EXISTS test_registration '
                            '(id SERIAL PRIMARY KEY, test_id INTEGER NOT NULL, '
                            'user_id INTEGER, name VARCHAR(120) NOT NULL, '
                            'email VARCHAR(120) NOT NULL, phone VARCHAR(15) DEFAULT \'\', '
                            'registered_at TIMESTAMP, '
                            'FOREIGN KEY(test_id) REFERENCES test(id), '
                            'FOREIGN KEY(user_id) REFERENCES "user"(id))'
                        ))
                    except Exception:
                        pass
                conn.commit()
        except Exception:
            pass
        seed_courses()
        seed_demo_test()
        seed_scheduled_tests()
        # Seed gallery with demo photos
        if GalleryPhoto.query.count() == 0:
            gallery_items = [
                dict(image_url='/static/images/WhatsApp Image 2026-03-27 at 2.15.29 PM.jpeg', caption='CCMC Knowledge & Study Centre — Students in session', order=1),
                dict(image_url='/static/images/WhatsApp Image 2026-03-27 at 2.15.30 PM.jpeg', caption='TNPSC coaching class at CCMC', order=2),
                dict(image_url='/static/images/WhatsApp Image 2026-03-27 at 2.15.32 PM.jpeg', caption='Expert faculty guiding students', order=3),
            ]
            for g in gallery_items:
                db.session.add(GalleryPhoto(**g))
            db.session.commit()
        # Seed centres
        if Centre.query.count() == 0:
            centres = [
                Centre(name='Knowledge & Study Centre', slug='ksc',
                       description='Our Knowledge & Study Center is dedicated to empowering students with quality education and structured learning methods. We provide expert guidance, updated study materials, and a focused environment to help learners achieve their goals.',
                       address='CCMC Knowledge & Study Centre, Addis St, Grey Town, ATT Colony, Gopalapuram, Coimbatore 641018',
                       order=1),
                Centre(name='Padaipagam I', slug='padaipagam-1',
                       description='Padaipagam is a creative learning space designed to nurture young minds through skill-based and engaging programs. We focus on developing creativity, logical thinking, and real-world skills in students.',
                       address='CCMC Knowledge Centre, Ganapathi Managar, Coimbatore',
                       order=2),
                Centre(name='Padaipagam II', slug='padaipagam-2',
                       description='Padaipagam is a vibrant platform that inspires students to discover their talents through innovative and activity-based learning. Every learner is encouraged to grow, create, and succeed in their own unique way.',
                       address='CCMC Knowledge Centre, Koundapalayam, Coimbatore',
                       order=3),
            ]
            for c in centres:
                db.session.add(c)
            db.session.commit()
        # Add Ukkadam centre if not exists
        if not Centre.query.filter_by(slug='ukkadam').first():
            db.session.add(Centre(
                name='Ukkadam', slug='ukkadam',
                description='A new CCMC learning centre coming soon to Ukkadam, Coimbatore. Stay tuned for updates.',
                address='Ukkadam, Coimbatore',
                order=4, is_active=True, coming_soon=True
            ))
            db.session.commit()
        # Ensure required centres exist with correct slugs (safe upsert)
        required_centres = [
            dict(slug='ksc', name='Knowledge & Study Centre',
                 address='CCMC Knowledge & Study Centre, Addis St, Grey Town, ATT Colony, Gopalapuram, Coimbatore 641018', order=1),
            dict(slug='padaipagam-1', name='Padaipagam I',
                 address='CCMC Knowledge Centre, Ganapathi Managar, Coimbatore', order=2),
            dict(slug='padaipagam-2', name='Padaipagam II',
                 address='CCMC Knowledge Centre, Koundapalayam, Coimbatore', order=3),
        ]
        for rc in required_centres:
            if not Centre.query.filter_by(slug=rc['slug']).first():
                db.session.add(Centre(name=rc['name'], slug=rc['slug'],
                                      address=rc['address'], order=rc['order'],
                                      is_active=True, coming_soon=False))
        db.session.commit()
        # Seed default categories
        if CourseCategory.query.count() == 0:
            defaults = [
                ('UPSC', 'UPSC Civil Services'), ('TNPSC', 'TNPSC'),
                ('RRB', 'RRB Railways'), ('SSC', 'SSC'),
                ('BANKING', 'Banking'), ('STATE PSC', 'State PSC'), ('TTP', 'TTP'),
            ]
            for i, (name, label) in enumerate(defaults):
                db.session.add(CourseCategory(name=name, label=label, order=i+1))
            db.session.commit()
        # Assign existing courses to KSC if they have no location
        ksc = Centre.query.filter_by(slug='ksc').first()
        if ksc:
            for course in Course.query.all():
                if not course.centres:
                    course.centres.append(ksc)
            db.session.commit()

        # Assign TNPSC courses to Padaipagam 1 and 2 centers
        padaipagam1 = Centre.query.filter_by(slug='padaipagam-1').first()
        padaipagam2 = Centre.query.filter_by(slug='padaipagam-2').first()

        if padaipagam1 and padaipagam2:
            tnpsc_courses = Course.query.filter_by(category='TNPSC').all()
            for course in tnpsc_courses:
                # Add to Padaipagam 1 if not already assigned
                if padaipagam1 not in course.centres:
                    course.centres.append(padaipagam1)
                # Add to Padaipagam 2 if not already assigned
                if padaipagam2 not in course.centres:
                    course.centres.append(padaipagam2)
            db.session.commit()
        # Seed testimonials
        if Testimonial.query.count() == 0:
            testimonials = [
                Testimonial(name='Karthik Selvam', role='TNPSC Group 2 Selected, Coimbatore',
                            content='CCMC\'s structured approach and dedicated faculty helped me clear TNPSC Group 2 in my first attempt. The test series and study material are excellent.',
                            rating=5, avatar_letter='K'),
                Testimonial(name='Priya Sundaram', role='Deputy Collector, TNPSC Group 1',
                            content='The test series and current affairs material at CCMC is unmatched. The faculty guidance was instrumental in my selection.',
                            rating=5, avatar_letter='P'),
                Testimonial(name='Rahul Murugan', role='RRB NTPC Selected, Coimbatore',
                            content='Cleared RRB NTPC in first attempt. The mock tests were exactly like the real exam. Highly recommend CCMC for railway exam preparation.',
                            rating=5, avatar_letter='R'),
                Testimonial(name='Meena Devi', role='SSC CGL Selected',
                            content='Best coaching for SSC in Coimbatore. The faculty is extremely knowledgeable and the study material is comprehensive.',
                            rating=5, avatar_letter='M'),
            ]
            for t in testimonials:
                db.session.add(t)
            db.session.commit()
        for camp in SummerCamp.query.all():
            if 'Ganapathi Managar' in camp.title and 'Padaipagam' not in camp.title:
                camp.title = 'Padaipagam 1 — Ganapathi Managar'
                camp.description = 'Padaipagam is a creative learning space designed to nurture young minds through skill-based and engaging programs.'
            elif 'Koundapalayam' in camp.title and 'Padaipagam' not in camp.title:
                camp.title = 'Padaipagam 2 — Koundapalayam'
                camp.description = 'Padaipagam is a vibrant platform that inspires students to discover their talents through innovative and activity-based learning.'
        db.session.commit()
        # Reset activities if they have old names
        if CampActivity.query.filter_by(name='Silambam').first() or CampActivity.query.filter_by(name='MS Word').first():
            CampActivity.query.delete()
            db.session.commit()
        # Seed site settings
        if SiteSettings.query.count() == 0:
            defaults = [
                ('site_name', 'CCMC', 'Site Name', 'text'),
                ('site_tagline', 'Knowledge & Study Centre — Coimbatore City Municipal Corporation', 'Site Tagline', 'text'),
                ('phone', '6385837858', 'Phone Number', 'text'),
                ('whatsapp', '916385837858', 'WhatsApp Number (with country code)', 'text'),
                ('email', 'commr.coimbatore@tn.gov.in', 'Email Address', 'text'),
                ('address', 'CCMC Knowledge & Study Centre, Addis St, Grey Town, ATT Colony, Gopalapuram, Coimbatore, Tamil Nadu 641018', 'Address', 'textarea'),
                ('working_hours', '7:00 AM – 9:00 PM ALL DAYS', 'Working Hours', 'text'),
                ('about_text', 'The Coimbatore City Municipal Corporation (CCMC) is the governing body responsible for the administration, infrastructure, and overall development of Coimbatore city. Through its Knowledge & Study Centres, CCMC facilitates competitive examination coaching, skill development programs, and training sessions.', 'About Text', 'textarea'),
                ('footer_text', 'The CCMC Knowledge & Study Centres provide free competitive exam coaching, skill development, and career training for all citizens of Coimbatore.', 'Footer Text', 'textarea'),
            ]
            for key, val, label, stype in defaults:
                db.session.add(SiteSettings(key=key, value=val, label=label, setting_type=stype))
            db.session.commit()
        # Seed hero banners from existing images
        if HeroBanner.query.count() == 0:
            banners = [
                dict(image_url='/static/images/WhatsApp Image 2026-03-27 at 2.15.29 PM.jpeg',
                     title='CCMC Knowledge & Study Centre',
                     subtitle='Empowering students with quality education and structured learning. Expert guidance for all competitive exams.',
                     badge='🎓 Knowledge & Study Centre', btn_text='Explore Courses', btn_link='/#featured-courses', order=1),
                dict(image_url='/static/images/WhatsApp Image 2026-03-27 at 2.15.30 PM.jpeg',
                     title='TTP — Transformation Training Program',
                     subtitle='A skill-focused program designed to enhance aptitude, reasoning, and problem-solving abilities for competitive success.',
                     badge='🎯 TTP Program', btn_text='Explore TTP', btn_link='/courses/ttp', order=2),
                dict(image_url='/static/images/WhatsApp Image 2026-03-27 at 2.15.32 PM.jpeg',
                     title='Padaipagam 1 — Ganapathi Managar',
                     subtitle='A creative learning space designed to nurture young minds through skill-based and engaging programs.',
                     badge='🎨 Padaipagam — Ganapathi Managar', btn_text='Explore Activities', btn_link='/summer-camp', order=3),
                dict(image_url='/static/images/WhatsApp Image 2026-03-27 at 2.15.36 PM.jpeg',
                     title='Padaipagam 2 — Koundapalayam',
                     subtitle='A vibrant platform inspiring students to discover their talents through innovative activity-based learning.',
                     badge='🎨 Padaipagam — Koundapalayam', btn_text='Explore Activities', btn_link='/summer-camp', order=4),
                dict(image_url='/static/images/WhatsApp Image 2026-03-27 at 2.15.39 PM.jpeg',
                     title='Summer Camp 2026',
                     subtitle='Fun, learning & creativity for kids at Ganapathi Managar and Koundapalayam. Chess, Abacus, Coding, Art and more!',
                     badge='🌞 Summer Camp 2026', btn_text='Register Now', btn_link='/summer-camp', order=5),
            ]
            for b in banners:
                db.session.add(HeroBanner(**b))
            db.session.commit()
        # Seed camp activities
        if CampActivity.query.count() == 0:
            activities = [
                # Padaipagam 1 activities
                dict(name='Chess', icon='♟️', tagline='Strategic thinking & concentration', order=1,
                     age_group='6–16 years', duration='1.5 hours/day',
                     image_url='https://images.unsplash.com/photo-1529699211952-734e80c4d42b?w=800&auto=format&fit=crop',
                     description='Enhance strategic thinking, concentration, and decision-making skills through expert-led chess training. Chess is proven to improve academic performance and logical reasoning in students.',
                     benefits='Strategic thinking\nConcentration & focus\nDecision-making skills\nMemory improvement'),
                dict(name='Tally with GST', icon='🧮', tagline='Accounting & GST fundamentals', order=2,
                     age_group='10–16 years', duration='2 hours/day',
                     image_url='https://images.unsplash.com/photo-1503676260728-1c00da094a0b?w=800&auto=format&fit=crop',
                     description='Learn accounting fundamentals and GST concepts with hands-on training using Tally software. One of India\'s most widely used accounting tools — a job-ready skill for commerce students.',
                     benefits='Tally software skills\nGST & accounting basics\nJob-ready skill\nHands-on practice'),
                dict(name='AI & Digital Marketing', icon='🤖', tagline='Future tech & online marketing', order=3,
                     age_group='12–16 years', duration='2 hours/day',
                     image_url='https://images.unsplash.com/photo-1516321318423-f06f85e504b3?w=800&auto=format&fit=crop',
                     description='Get introduced to Artificial Intelligence and modern digital marketing tools and strategies. Learn how AI is shaping the future and how to use digital platforms for business growth.',
                     benefits='AI fundamentals\nDigital marketing skills\nSocial media strategy\nFuture-ready career skills'),
                dict(name='Abacus', icon='🔢', tagline='Mental math & concentration', order=4,
                     age_group='6–12 years', duration='1.5 hours/day',
                     image_url='https://images.unsplash.com/photo-1588072432836-e10032774350?w=800&auto=format&fit=crop',
                     description='Improve mental math skills, memory, and concentration through structured abacus training. Using the ancient abacus tool, kids learn to perform complex calculations mentally at lightning speed.',
                     benefits='Faster mental calculation\nImproved concentration\nBetter academic performance\nIncreased confidence in maths'),
                # Padaipagam 2 activities
                dict(name='Mandala Art', icon='🎨', tagline='Creativity & mindfulness', order=5,
                     age_group='6–16 years', duration='1.5 hours/day',
                     image_url='https://images.unsplash.com/photo-1513364776144-60967b0f800f?w=800&auto=format&fit=crop',
                     description='Explore creativity and mindfulness through mandala art, enhancing focus, patience, and artistic expression. Students create beautiful geometric patterns while developing concentration and fine motor skills.',
                     benefits='Creative expression\nMindfulness & focus\nPatience & attention to detail\nArtistic skills'),
                dict(name='STEM', icon='🔬', tagline='Science, Technology, Engineering & Maths', order=6,
                     age_group='8–16 years', duration='2 hours/day',
                     image_url='https://images.unsplash.com/photo-1560785496-3c9d27877182?w=800&auto=format&fit=crop',
                     description='Hands-on learning in Science, Technology, Engineering, and Mathematics to build innovation and problem-solving skills. Students work on real projects and experiments that make learning exciting.',
                     benefits='Problem-solving skills\nScientific thinking\nInnovation & creativity\nFoundation for STEM careers'),
                dict(name='Junior Coders', icon='💻', tagline='Fun programming for kids', order=7,
                     age_group='8–14 years', duration='2 hours/day',
                     image_url='https://images.unsplash.com/photo-1509062522246-3755977927d7?w=800&auto=format&fit=crop',
                     description='An introductory coding program for kids to develop logical thinking and basic programming skills in a fun way. Using visual tools like Scratch and basic Python to create games and animations.',
                     benefits='Logical thinking\nBasic programming skills\nCreate games & animations\nFuture tech foundation'),
                dict(name='Acrylic & Sketch', icon='🖌️', tagline='Drawing & painting techniques', order=8,
                     age_group='6–16 years', duration='2 hours/day',
                     image_url='https://images.unsplash.com/photo-1513364776144-60967b0f800f?w=800&auto=format&fit=crop',
                     description='Learn drawing and painting techniques to express creativity through acrylic colors and sketching. Students create their own artworks inspired by Tamil Nadu\'s rich culture and nature.',
                     benefits='Drawing & sketching skills\nColour theory\nCreative expression\nTake-home artwork'),
            ]
            for a in activities:
                db.session.add(CampActivity(**a))
            db.session.commit()
        # Seed summer camps
        if SummerCamp.query.count() == 0:
            camps_data = [
                dict(title='Padaipagam 1 — Ganapathi Managar', location='CCMC Knowledge Centre, Ganapathi Managar, Coimbatore',
                     description='Padaipagam is a creative learning space designed to nurture young minds through skill-based and engaging programs. We focus on developing creativity, logical thinking, and real-world skills in students.',
                     start_date='May 15, 2026', end_date='June 15, 2026', age_group='6–16 years'),
                dict(title='Padaipagam 2 — Koundapalayam', location='CCMC Knowledge Centre, Koundapalayam, Coimbatore',
                     description='Padaipagam is a vibrant platform that inspires students to discover their talents through innovative and activity-based learning. Every learner is encouraged to grow, create, and succeed in their own unique way.',
                     start_date='May 15, 2026', end_date='June 15, 2026', age_group='6–16 years'),
            ]
            gallery_photos = [
                ('https://images.unsplash.com/photo-1503676260728-1c00da094a0b?w=800&auto=format&fit=crop', 'Kids learning abacus'),
                ('https://images.unsplash.com/photo-1588072432836-e10032774350?w=800&auto=format&fit=crop', 'Children in classroom'),
                ('https://images.unsplash.com/photo-1513364776144-60967b0f800f?w=800&auto=format&fit=crop', 'Art and creativity'),
                ('https://images.unsplash.com/photo-1516321318423-f06f85e504b3?w=800&auto=format&fit=crop', 'Computer skills training'),
                ('https://images.unsplash.com/photo-1560785496-3c9d27877182?w=800&auto=format&fit=crop', 'South Indian students'),
                ('https://images.unsplash.com/photo-1509062522246-3755977927d7?w=800&auto=format&fit=crop', 'Summer camp activities'),
            ]
            for camp_data in camps_data:
                camp = SummerCamp(**camp_data)
                db.session.add(camp)
                db.session.flush()
                for url, caption in gallery_photos:
                    db.session.add(CampGallery(camp_id=camp.id, image_url=url, caption=caption))
            db.session.commit()
        if not User.query.filter_by(email='admin@ccmc.com').first():
            admin_user = User(name='Admin', email='admin@ccmc.com',
                              password=generate_password_hash('admin123'),
                              is_admin=True, is_verified=True)
            db.session.add(admin_user)
            db.session.commit()
            print('Admin created: admin@ccmc.com / admin123')
        else:
            # Only ensure admin flag and verified — never reset password
            admin = User.query.filter_by(email='admin@ccmc.com').first()
            if not admin.is_verified or not admin.is_admin:
                admin.is_verified = True
                admin.is_admin = True
                db.session.commit()

init_db()

@app.route('/admin/student/<int:user_id>')
@login_required
@admin_required
def admin_student_detail(user_id):
    user = User.query.get_or_404(user_id)
    enrollments = Enrollment.query.filter_by(user_id=user_id).all()
    attempts = TestAttempt.query.filter_by(user_id=user_id).order_by(TestAttempt.submitted_at.desc()).all()
    return render_template('admin_student_detail.html', student=user, enrollments=enrollments, attempts=attempts)

# ── Summer Camp Routes ─────────────────────────────────────────────────────────
@app.route('/summer-camp')
def summer_camp():
    camps = SummerCamp.query.filter_by(is_active=True).all()
    activities = CampActivity.query.filter_by(is_active=True).order_by(CampActivity.order).all()
    return render_template('summer_camp.html', camps=camps, activities=activities)

@app.route('/summer-camp/activity/<int:act_id>')
def activity_detail(act_id):
    activity = CampActivity.query.get_or_404(act_id)
    camps = SummerCamp.query.filter_by(is_active=True).all()
    return render_template('activity_detail.html', activity=activity, camps=camps)

@app.route('/summer-camp/<int:camp_id>/enquiry', methods=['POST'])
def camp_enquiry(camp_id):
    enq = CampEnquiry(
        camp_id=camp_id,
        child_name=request.form.get('child_name',''),
        parent_name=request.form.get('parent_name',''),
        mobile=request.form.get('mobile',''),
        email=request.form.get('email',''),
        age=request.form.get('age',''),
        activity=request.form.get('activity',''),
        message=request.form.get('message','')
    )
    db.session.add(enq)
    db.session.commit()
    flash('Enquiry submitted! We will contact you shortly.', 'success')
    return redirect(url_for('summer_camp'))

@app.route('/admin/summer-camp')
@login_required
@admin_required
def admin_summer_camp():
    camps = SummerCamp.query.order_by(SummerCamp.created_at.desc()).all()
    enquiries = CampEnquiry.query.order_by(CampEnquiry.created_at.desc()).all()
    activities = CampActivity.query.order_by(CampActivity.order).all()
    return render_template('admin_summer_camp.html', camps=camps, enquiries=enquiries, activities=activities)

@app.route('/admin/summer-camp/add', methods=['POST'])
@login_required
@admin_required
def admin_add_camp():
    camp = SummerCamp(
        title=request.form.get('title'),
        location=request.form.get('location'),
        description=request.form.get('description',''),
        start_date=request.form.get('start_date',''),
        end_date=request.form.get('end_date',''),
        age_group=request.form.get('age_group','')
    )
    db.session.add(camp)
    db.session.commit()
    flash('Summer camp added!', 'success')
    return redirect(url_for('admin_summer_camp'))

@app.route('/admin/summer-camp/gallery/add/<int:camp_id>', methods=['POST'])
@login_required
@admin_required
def admin_add_gallery(camp_id):
    caption = request.form.get('caption', '')
    image_url = None
    # Try file upload first
    if 'image_file' in request.files and request.files['image_file'].filename:
        image_url = upload_image(request.files['image_file'])
    # Fallback to URL if provided
    if not image_url:
        image_url = request.form.get('image_url', '')
    if image_url:
        db.session.add(CampGallery(camp_id=camp_id, image_url=image_url, caption=caption))
        db.session.commit()
        flash('Photo added!', 'success')
    else:
        flash('Please upload a photo or provide a URL. (Set up Cloudinary for file uploads)', 'error')
    return redirect(url_for('admin_summer_camp'))

@app.route('/admin/summer-camp/gallery/delete/<int:img_id>', methods=['POST'])
@login_required
@admin_required
def admin_delete_gallery(img_id):
    db.session.delete(CampGallery.query.get_or_404(img_id))
    db.session.commit()
    return redirect(url_for('admin_summer_camp'))

@app.route('/admin/summer-camp/delete/<int:camp_id>', methods=['POST'])
@login_required
@admin_required
def admin_delete_camp(camp_id):
    db.session.delete(SummerCamp.query.get_or_404(camp_id))
    db.session.commit()
    flash('Camp deleted.', 'success')
    return redirect(url_for('admin_summer_camp'))

@app.route('/admin/activity/add', methods=['POST'])
@login_required
@admin_required
def admin_add_activity():
    image_url = None
    if 'image_file' in request.files and request.files['image_file'].filename:
        image_url = upload_image(request.files['image_file'])
    if not image_url:
        image_url = request.form.get('image_url', '')
    act = CampActivity(
        name=request.form.get('name'),
        icon=request.form.get('icon','🎯'),
        tagline=request.form.get('tagline',''),
        description=request.form.get('description',''),
        age_group=request.form.get('age_group',''),
        duration=request.form.get('duration',''),
        benefits=request.form.get('benefits',''),
        image_url=image_url,
        order=int(request.form.get('order',99))
    )
    db.session.add(act)
    db.session.commit()
    flash('Activity added!', 'success')
    return redirect(url_for('admin_summer_camp'))

@app.route('/admin/activity/edit/<int:act_id>', methods=['POST'])
@login_required
@admin_required
def admin_edit_activity(act_id):
    act = CampActivity.query.get_or_404(act_id)
    image_url = None
    if 'image_file' in request.files and request.files['image_file'].filename:
        image_url = upload_image(request.files['image_file'])
    act.name = request.form.get('name', act.name)
    act.icon = request.form.get('icon', act.icon)
    act.tagline = request.form.get('tagline', act.tagline)
    act.description = request.form.get('description', act.description)
    act.age_group = request.form.get('age_group', act.age_group)
    act.duration = request.form.get('duration', act.duration)
    act.benefits = request.form.get('benefits', act.benefits)
    if image_url:
        act.image_url = image_url
    elif request.form.get('image_url'):
        act.image_url = request.form.get('image_url')
    db.session.commit()
    flash(f'{act.name} updated!', 'success')
    return redirect(url_for('admin_summer_camp'))

@app.route('/admin/activity/delete/<int:act_id>', methods=['POST'])
@login_required
@admin_required
def admin_delete_activity(act_id):
    db.session.delete(CampActivity.query.get_or_404(act_id))
    db.session.commit()
    flash('Activity deleted.', 'success')
    return redirect(url_for('admin_summer_camp'))

# ── CMS Routes ─────────────────────────────────────────────────────────────────
@app.route('/admin/cms')
@login_required
@admin_required
def admin_cms():
    db.create_all()
    try:
        banners = HeroBanner.query.order_by(HeroBanner.order).all()
    except Exception:
        banners = []
    try:
        cms_settings = SiteSettings.query.order_by(SiteSettings.id).all()
    except Exception:
        cms_settings = []
    try:
        activities = CampActivity.query.order_by(CampActivity.order).all()
    except Exception:
        activities = []
    # Seed settings if empty
    if not cms_settings:
        try:
            defaults = [
                ('site_name', 'CCMC', 'Site Name', 'text'),
                ('phone', '6385837858', 'Phone Number', 'text'),
                ('email', 'commr.coimbatore@tn.gov.in', 'Email Address', 'text'),
                ('address', 'CCMC Knowledge & Study Centre, Addis St, Gopalapuram, Coimbatore 641018', 'Address', 'textarea'),
                ('working_hours', '7:00 AM – 9:00 PM ALL DAYS', 'Working Hours', 'text'),
                ('about_text', 'The Coimbatore City Municipal Corporation (CCMC) provides free coaching and skill development.', 'About Text', 'textarea'),
                ('footer_text', 'Free competitive exam coaching for all citizens of Coimbatore.', 'Footer Text', 'textarea'),
            ]
            for key, val, label, stype in defaults:
                if not SiteSettings.query.filter_by(key=key).first():
                    db.session.add(SiteSettings(key=key, value=val, label=label, setting_type=stype))
            db.session.commit()
            cms_settings = SiteSettings.query.order_by(SiteSettings.id).all()
        except Exception:
            pass
    # Pass as cms_settings (not settings) to avoid overriding context processor
    return render_template('admin_cms.html', banners=banners, cms_settings=cms_settings, activities=activities)

# Hero Banner
@app.route('/admin/cms/banner/add', methods=['POST'])
@login_required
@admin_required
def admin_add_banner():
    image_url = None
    if 'image_file' in request.files and request.files['image_file'].filename:
        image_url = upload_image(request.files['image_file'])
    if not image_url:
        image_url = request.form.get('image_url', '')
    if not image_url:
        flash('Please upload an image.', 'error')
        return redirect(url_for('admin_cms'))
    order = HeroBanner.query.count() + 1
    banner = HeroBanner(
        image_url=image_url,
        title=request.form.get('title', ''),
        subtitle=request.form.get('subtitle', ''),
        badge=request.form.get('badge', ''),
        btn_text=request.form.get('btn_text', 'Explore Courses'),
        btn_link=request.form.get('btn_link', '#'),
        order=order
    )
    db.session.add(banner)
    db.session.commit()
    flash('Banner added!', 'success')
    return redirect(url_for('admin_cms'))

@app.route('/admin/cms/banner/delete/<int:bid>', methods=['POST'])
@login_required
@admin_required
def admin_delete_banner(bid):
    db.session.delete(HeroBanner.query.get_or_404(bid))
    db.session.commit()
    flash('Banner deleted.', 'success')
    return redirect(url_for('admin_cms'))

@app.route('/admin/cms/banner/toggle/<int:bid>', methods=['POST'])
@login_required
@admin_required
def admin_toggle_banner(bid):
    b = HeroBanner.query.get_or_404(bid)
    b.is_active = not b.is_active
    db.session.commit()
    return redirect(url_for('admin_cms'))

# Activity Photos (multiple per activity)
@app.route('/admin/cms/activity-photo/add/<int:act_id>', methods=['POST'])
@login_required
@admin_required
def admin_add_activity_photo(act_id):
    files = request.files.getlist('image_files')
    added = 0
    for f in files:
        if f and f.filename:
            url = upload_image(f)
            if url:
                caption = request.form.get('caption', '')
                order = ActivityPhoto.query.filter_by(activity_id=act_id).count() + 1
                db.session.add(ActivityPhoto(activity_id=act_id, image_url=url, caption=caption, order=order))
                added += 1
    db.session.commit()
    flash(f'{added} photo(s) added!', 'success')
    return redirect(url_for('admin_cms'))

@app.route('/admin/cms/activity-photo/delete/<int:pid>', methods=['POST'])
@login_required
@admin_required
def admin_delete_activity_photo(pid):
    db.session.delete(ActivityPhoto.query.get_or_404(pid))
    db.session.commit()
    return redirect(url_for('admin_cms'))

# Site Settings
@app.route('/admin/cms/settings/save', methods=['POST'])
@login_required
@admin_required
def admin_save_settings():
    for key in request.form:
        if key.startswith('setting_'):
            setting_key = key[8:]  # strip 'setting_'
            s = SiteSettings.query.filter_by(key=setting_key).first()
            if s:
                s.value = request.form.get(key, '')
    db.session.commit()
    flash('Settings saved!', 'success')
    return redirect(url_for('admin_cms'))

@app.route('/centre/<slug>')
def centre_detail(slug):
    centre = Centre.query.filter_by(slug=slug, is_active=True).first_or_404()
    if centre.coming_soon:
        enrolled_ids = []
        return render_template('centre.html', centre=centre, courses=[], activities=[], enrolled_ids=enrolled_ids)
    # Show only courses assigned to this centre
    courses = [c for c in centre.courses if c.is_active]
    activities = CampActivity.query.filter_by(is_active=True).order_by(CampActivity.order).all()
    enrolled_ids = [e.course_id for e in current_user.enrollments] if current_user.is_authenticated else []
    return render_template('centre.html', centre=centre, courses=courses, activities=activities, enrolled_ids=enrolled_ids)

@app.route('/gallery')
def gallery():
    try:
        photos = GalleryPhoto.query.filter_by(is_active=True).order_by(GalleryPhoto.order).all()
    except Exception:
        photos = []
    camps = SummerCamp.query.filter_by(is_active=True).all()
    return render_template('gallery.html', photos=photos, camps=camps)

@app.route('/testimonials')
def testimonials():
    items = Testimonial.query.filter_by(is_active=True).all()
    return render_template('testimonials.html', items=items)

@app.route('/course/<int:course_id>/videos')
@login_required
def course_videos(course_id):
    course = Course.query.get_or_404(course_id)
    enrolled = Enrollment.query.filter_by(user_id=current_user.id, course_id=course_id).first()
    if not enrolled:
        flash('Enroll in this course to access recorded classes.', 'error')
        return redirect(url_for('course_detail', course_id=course_id))
    videos = CourseVideo.query.filter_by(course_id=course_id, is_active=True).order_by(CourseVideo.order).all()
    materials = CourseMaterial.query.filter_by(course_id=course_id, is_active=True).order_by(CourseMaterial.order).all()
    return render_template('course_videos.html', course=course, videos=videos, materials=materials)

# Admin video management
@app.route('/admin/course/<int:course_id>/video/add', methods=['POST'])
@login_required
@admin_required
def admin_add_video(course_id):
    title       = request.form.get('title', '').strip()
    description = request.form.get('description', '').strip()
    video_url   = None

    # Try Cloudinary video upload first
    if CLOUDINARY_ENABLED and 'video_file' in request.files and request.files['video_file'].filename:
        f = request.files['video_file']
        try:
            result = cloudinary.uploader.upload(
                f,
                folder='ccmc/videos',
                resource_type='video',
                chunk_size=6000000          # 6 MB chunks for large files
            )
            video_url = result.get('secure_url')
        except Exception as e:
            print(f'Cloudinary video upload error: {e}')
            flash(f'Upload failed: {e}', 'error')
            return redirect(url_for('admin_course_videos', course_id=course_id))

    # Fallback: manual YouTube embed URL
    if not video_url:
        video_url = request.form.get('video_url', '').strip()

    if not title or not video_url:
        flash('Title and video are required.', 'error')
        return redirect(url_for('admin_course_videos', course_id=course_id))

    video = CourseVideo(
        course_id=course_id, title=title, description=description,
        video_url=video_url,
        order=CourseVideo.query.filter_by(course_id=course_id).count() + 1
    )
    db.session.add(video)
    db.session.commit()
    flash('Video uploaded successfully!', 'success')
    return redirect(url_for('admin_course_videos', course_id=course_id))

@app.route('/admin/course/<int:course_id>/videos')
@login_required
@admin_required
def admin_course_videos(course_id):
    course = Course.query.get_or_404(course_id)
    videos = CourseVideo.query.filter_by(course_id=course_id).order_by(CourseVideo.order).all()
    materials = CourseMaterial.query.filter_by(course_id=course_id).order_by(CourseMaterial.order).all()
    return render_template('admin_course_videos.html', course=course, videos=videos, materials=materials)

@app.route('/admin/video/delete/<int:vid>', methods=['POST'])
@login_required
@admin_required
def admin_delete_video(vid):
    db.session.delete(CourseVideo.query.get_or_404(vid))
    db.session.commit()
    flash('Video deleted.', 'success')
    return redirect(request.referrer or url_for('admin'))

# ── Course Materials (PDF) ─────────────────────────────────────────────────────
MATERIAL_UPLOAD_FOLDER = os.path.join('static', 'uploads', 'materials')
os.makedirs(MATERIAL_UPLOAD_FOLDER, exist_ok=True)
MATERIAL_EXTENSIONS = {'pdf', 'doc', 'docx', 'ppt', 'pptx'}

def allowed_material(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in MATERIAL_EXTENSIONS

@app.route('/admin/course/<int:course_id>/materials/add', methods=['POST'])
@login_required
@admin_required
def admin_add_material(course_id):
    course = Course.query.get_or_404(course_id)
    title = request.form.get('title', '').strip()
    description = request.form.get('description', '').strip()
    file_url = None
    file_type = 'pdf'

    # Try Cloudinary first
    if CLOUDINARY_ENABLED and 'material_file' in request.files and request.files['material_file'].filename:
        f = request.files['material_file']
        if allowed_material(f.filename):
            try:
                result = cloudinary.uploader.upload(f, folder='ccmc/materials', resource_type='raw')
                file_url = result.get('secure_url')
                file_type = f.filename.rsplit('.', 1)[1].lower()
            except Exception as e:
                print(f'Cloudinary material upload error: {e}')

    # Fallback: save locally
    if not file_url and 'material_file' in request.files and request.files['material_file'].filename:
        f = request.files['material_file']
        if allowed_material(f.filename):
            filename = secure_filename(f.filename)
            save_path = os.path.join(MATERIAL_UPLOAD_FOLDER, filename)
            f.save(save_path)
            file_url = '/' + save_path.replace('\\', '/')
            file_type = filename.rsplit('.', 1)[1].lower()

    if not file_url or not title:
        flash('Title and file are required.', 'error')
        return redirect(url_for('admin_course_videos', course_id=course_id))

    mat = CourseMaterial(
        course_id=course_id, title=title, description=description,
        file_url=file_url, file_type=file_type,
        order=CourseMaterial.query.filter_by(course_id=course_id).count() + 1
    )
    db.session.add(mat)
    db.session.commit()
    flash('Material uploaded!', 'success')
    return redirect(url_for('admin_course_videos', course_id=course_id))

@app.route('/admin/material/delete/<int:mid>', methods=['POST'])
@login_required
@admin_required
def admin_delete_material(mid):
    db.session.delete(CourseMaterial.query.get_or_404(mid))
    db.session.commit()
    flash('Material deleted.', 'success')
    return redirect(request.referrer or url_for('admin'))


@app.route('/admin/gallery/add', methods=['POST'])
@login_required
@admin_required
def admin_add_gallery_photo():
    image_url = None
    if 'image_file' in request.files and request.files['image_file'].filename:
        image_url = upload_image(request.files['image_file'])
    if not image_url:
        image_url = request.form.get('image_url','')
    if image_url:
        photo = GalleryPhoto(
            image_url=image_url,
            caption=request.form.get('caption',''),
            category=request.form.get('category','general'),
            order=GalleryPhoto.query.count() + 1
        )
        db.session.add(photo)
        db.session.commit()
        flash('Photo added to gallery!', 'success')
    return redirect(url_for('admin_gallery'))

@app.route('/admin/gallery')
@login_required
@admin_required
def admin_gallery():
    photos = GalleryPhoto.query.order_by(GalleryPhoto.order).all()
    return render_template('admin_gallery.html', photos=photos)

@app.route('/admin/gallery/delete/<int:pid>', methods=['POST'])
@login_required
@admin_required
def admin_delete_gallery_photo(pid):
    db.session.delete(GalleryPhoto.query.get_or_404(pid))
    db.session.commit()
    return redirect(url_for('admin_gallery'))

# Admin testimonials
@app.route('/admin/testimonials')
@login_required
@admin_required
def admin_testimonials():
    items = Testimonial.query.order_by(Testimonial.created_at.desc()).all()
    return render_template('admin_testimonials.html', items=items)

@app.route('/admin/testimonial/add', methods=['POST'])
@login_required
@admin_required
def admin_add_testimonial():
    t = Testimonial(
        name=request.form.get('name'),
        role=request.form.get('role',''),
        content=request.form.get('content'),
        rating=int(request.form.get('rating',5)),
        avatar_letter=request.form.get('name','A')[0].upper()
    )
    db.session.add(t)
    db.session.commit()
    flash('Testimonial added!', 'success')
    return redirect(url_for('admin_testimonials'))

@app.route('/admin/testimonial/delete/<int:tid>', methods=['POST'])
@login_required
@admin_required
def admin_delete_testimonial(tid):
    db.session.delete(Testimonial.query.get_or_404(tid))
    db.session.commit()
    return redirect(url_for('admin_testimonials'))

if __name__ == '__main__':
    app.run(debug=True)

