# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError, Warning
from odoo.tools.misc import format_date, format_datetime
#import pytz

DEFAULT_TIMEZONE = 'America/Lima'

#def local_datetime(untimed_datetime, timezone) :
#    return untimed_datetime.astimezone(pytz.timezone(timezone))

class PlannerProfessional(models.Model) :
    _name = 'planner.professional'
    _description = 'Professional'
    _rec_name = 'employee_id'
    
    employee_id = fields.Many2one(comodel_name='hr.employee', string='Employee', required=True)
    procedure_ids = fields.Many2many(comodel_name='product.product', string='Procedures', domain=[('type','=','service')])

class PlannerSpot(models.Model) :
    _name = 'planner.spot'
    _description = 'Spot'
    
    def _get_default_timezone(self) :
        #datetime.datetime.now(pytz.timezone('America/Lima')).utcoffset()
        return DEFAULT_TIMEZONE
    
    name = fields.Char(string='Planner', readonly=True, copy=False, default='/')
    professional_id = fields.Many2one(comodel_name='planner.professional', string='Professional')
    date = fields.Date(string='Date')
    start = fields.Datetime(string='Start')
    end = fields.Datetime(string='End')
    spots = fields.Integer(string='Spots', default=1, required=True)
    planner_ids = fields.One2many(comodel_name='planner.planner', inverse_name='spot_id', string='Planners')
    available_spots = fields.Integer(string='Available Spots', compute='_compute_available_spots', store=True)
    
    @api.depends('spots', 'planner_ids')
    def _compute_available_spots(self) :
        for record in self :
            if record.spots - len(record.planner_ids) :
                raise UserError('Error')
            record.available_spots = record.spots - len(record.planner_ids)
    
    @api.depends('professional_id', 'date', 'start', 'end')
    def name_get(self) :
        result = []
        current_tz = self.env.user.tz or self._get_default_timezone()
        for spot in self :
            name = '/'
            if spot.professional_id and spot.date and spot.start and spot.end :
                name = (spot.professional_id.display_name,
                        format_date(self.env, planner.date, date_format='dd/MM/Y'),
                        format_datetime(self.env, spot.start, tz=current_tz, dt_format='HH:mm:ss'),
                        format_datetime(self.env, spot.end, tz=current_tz, dt_format='HH:mm:ss'))
                name = ('%s: %s %s - %s') % name
            result.append((spot.id, name))
        return result

class PlannerProfessionalAvailability(models.Model) :
    _name = 'planner.professional.availability'
    _description = 'Availability'
    
    def _get_default_timezone(self) :
        return DEFAULT_TIMEZONE
    
    name = fields.Char(string='Availability', required=True, readonly=True, copy=False, default='/')
    professional_id = fields.Many2one(comodel_name='planner.professional', string='Professional', required=True)
    day = fields.Selection(selection=[('1','Monday'),('2','Tuesday'),('3','Wednesday'),('4','Thursday'),('5','Friday'),('6','Saturday'),('7','Sunday')],
                           string='Day', default='1', required=True)
    start = fields.Float(string='Start', required=True)
    end = fields.Float(string='End', required=True)
    duration = fields.Float(string='Duration', default=0.5, required=True)
    spots = fields.Integer(string='Spots', default=1, required=True)
    
    @api.depends('professional_id', 'day', 'start', 'end')
    def name_get(self) :
        result = []
        current_tz = self.env.user.tz or self._get_default_timezone()
        for avail in self :
            name = '/'
            if avail.professional_id and avail.day :
                
                name = (avail.professional_id.display_name,
                        dict(self._fields['day'].selection)[avail.day],
                        format_datetime(self.env, avail.start, tz=current_tz, dt_format='HH:mm:ss'),
                        format_datetime(self.env, avail.end, tz=current_tz, dt_format='HH:mm:ss'))
                name = ('%s: %s %s - %s') % name
            result.append((avail.id, name))
        return result

class PlannerPlanner(models.Model) :
    _name = 'planner.planner'
    _description = 'Planner'
    
    def _get_default_timezone(self) :
        return DEFAULT_TIMEZONE
    
    name = fields.Char(string='Planner', readonly=True, copy=False, default='/')
    state = fields.Selection(string='Status', required=True, readonly=True, copy=False, tracking=True, default='planned',
                             selection=[('planned','Planned'),('received','Received'),('attended','Attended'),('cancel','Cancelled')])
    received = fields.Boolean(string='Received')
    patient_id = fields.Many2one(comodel_name='res.partner', string='Patient')
    professional_id = fields.Many2one(comodel_name='planner.professional', string='Professional')
    procedure_ids = fields.Many2many(comodel_name='product.product', string='Procedures', compute='_compute_professional_id', store=True)
    procedure_id = fields.Many2one(comodel_name='product.product', string='Procedure')
    spot_id = fields.Many2one(comodel_name='planner.spot', string='Spot', domain=[('available_spots','>',0)])
    date = fields.Date(string='Date', compute='_compute_spot_id', store=True, readonly=True)
    start = fields.Datetime(string='Start', compute='_compute_spot_id', store=True, readonly=True)
    end = fields.Datetime(string='End', compute='_compute_spot_id', store=True, readonly=True)
    
    @api.depends('spot_id')
    def _compute_spot_id(self) :
        for record in self :
            record.date = record.spot_id.date
            record.start = record.spot_id.start
            record.end = record.spot_id.end
    
    @api.depends('professional_id')
    def _compute_professional_id(self) :
        for record in self :
            record.procedure_ids = record.professional_id.procedure_ids
    
    @api.depends('patient_id', 'professional_id', 'date', 'start', 'end')
    def name_get(self) :
        result = []
        current_tz = self.env.user.tz or self._get_default_timezone()
        for planner in self :
            name = '/'
            if planner.patient_id and planner.professional_id and planner.date and planner.start and planner.end :
                #local_start = local_datetime(planner.start, current_tz)
                #local_end = local_datetime(planner.end, current_tz)
                name = (planner.patient_id.name,
                        planner.professional_id.display_name,
                        planner.procedure_id.name,
                        #planner.date.strftime('%d/%m/%Y'),
                        format_date(self.env, planner.date, date_format='dd/MM/Y'),
                        #local_start.strftime('%H:%M:%S'),
                        #local_end.strftime('%H:%M:%S'))
                        format_datetime(self.env, planner.start, tz=current_tz, dt_format='HH:mm:ss'),
                        format_datetime(self.env, planner.end, tz=current_tz, dt_format='HH:mm:ss'))
                name = _('Appointment from %s with %s for %s on the %s from %s to %s') % name
            result.append((planner.id, name))
        return result
