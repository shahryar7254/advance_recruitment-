from odoo import models, fields, api

class AdvancedRecruitmentResume(models.Model):
    _name = "advanced_recruitment.resume"
    _description = "Candidate Resume"
    _order = "score desc"

    candidate_name = fields.Char("Candidate Name", required=True, default="Candidate")
    email = fields.Char("Email")
    phone = fields.Char("Phone")
    source_filename = fields.Char("Source File")
    score = fields.Float("Matching Score", digits=(6, 2))
    raw_text = fields.Text("Raw Text")
    cv_file = fields.Binary("CV File")
    application_date = fields.Datetime("Application Date", default=lambda self: fields.Datetime.now())
    status = fields.Selection([
        ('excellent', 'Excellent (90%+)'),
        ('best', 'Best (80-89%)'),
        ('good', 'Good (70-79%)'),
        ('average', 'Average (60-69%)'),
        ('normal', 'Normal (45-59%)'),
        ('poor', 'Poor (Below 45%)')
    ], string="Status", compute='_compute_status', store=True)

    @api.depends('score')
    def _compute_status(self):
        for record in self:
            if record.score >= 90:
                record.status = 'excellent'
            elif record.score >= 80:
                record.status = 'best'
            elif record.score >= 70:
                record.status = 'good'
            elif record.score >= 60:
                record.status = 'average'
            elif record.score >= 45:
                record.status = 'normal'
            else:
                record.status = 'poor'