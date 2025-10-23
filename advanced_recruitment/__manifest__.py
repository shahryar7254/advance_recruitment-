{
    'name': 'Advanced Recruitment',
    'version': '18.0.1.0.0',
    'category': 'Human Resources',
    'summary': 'Advanced CV Scanning with AI Matching',
    'description': """
        AI-powered CV scanning and matching system using Gemini AI.
    """,
    'author': 'Raja Shahryar Shabeer',
    'website': 'https://www.fidsor.com',
    'depends': ['base'],
    'data': [
        'security/ir.model.access.csv',
        'views/resume_views.xml',
        'views/cv_scan_wizard_views.xml',
    ],
    'external_dependencies': {
        'python': ['requests', 'fitz', 'pymupdf', 'python-docx'],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}