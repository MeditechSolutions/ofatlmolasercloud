# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError, Warning
from odoo.tools.misc import format_date, format_datetime
import datetime
import pytz

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
    active = fields.Boolean(string='Active', default=True)
    professional_id = fields.Many2one(comodel_name='planner.professional', string='Professional')
    date = fields.Date(string='Date', required=True)
    start = fields.Datetime(string='Start', required=True)
    end = fields.Datetime(string='End', required=True)
    spots = fields.Integer(string='Spots', default=1, required=True)
    planner_ids = fields.One2many(comodel_name='planner.planner', inverse_name='spot_id', string='Planners')
    available_spots = fields.Integer(string='Available Spots', compute='_compute_available_spots', store=True)
    
    @api.depends('spots', 'planner_ids')
    def _compute_available_spots(self) :
        for record in self :
            if (record.spots - len(record.planner_ids)) < 0 :
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
                        format_date(self.env, spot.date, date_format='dd/MM/Y'),
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
    
    name = fields.Char(string='Availability', readonly=True, copy=False, default='/')
    professional_id = fields.Many2one(comodel_name='planner.professional', string='Professional', required=True)
    day = fields.Selection(selection=[('1','Monday'),('2','Tuesday'),('3','Wednesday'),('4','Thursday'),('5','Friday'),('6','Saturday'),('7','Sunday')],
                           string='Day', default='1', required=True)
    start = fields.Float(string='Start', default=8)
    end = fields.Float(string='End', default=18)
    duration = fields.Float(string='Duration', default=0.5, required=True)
    spots = fields.Integer(string='Spots', default=1, required=True)
    
    @api.depends('professional_id', 'day', 'start', 'end')
    def name_get(self) :
        result = []
        current_tz = self.env.user.tz or self._get_default_timezone()
        current_offset = datetime.datetime.now(pytz.timezone(current_tz)).utcoffset()
        for avail in self :
            name = '/'
            if avail.professional_id and avail.day :
                start = datetime.datetime.combine(datetime.date.today(), datetime.datetime.min.time())
                end = start + datetime.timedelta(hours=avail.end) - current_offset
                start = start + datetime.timedelta(hours=avail.start) - current_offset
                name = (avail.professional_id.display_name,
                        dict(self._fields['day'].selection)[avail.day],
                        format_datetime(self.env, start, tz=current_tz, dt_format='HH:mm'),
                        format_datetime(self.env, end, tz=current_tz, dt_format='HH:mm'))
                name = ('%s: %s %s - %s') % name
            result.append((avail.id, name))
        return result
    
    def spot_creation(self, availability_record=False) :
        current_tz = self.env.user.tz or self._get_default_timezone()
        current_offset = datetime.datetime.now(pytz.timezone(current_tz)).utcoffset()
        aware_now = fields.Datetime.now().astimezone(pytz.timezone(current_tz))
        #aware_today = aware_now.date()
        spot = self.env['planner.spot'].sudo()
        for record in (availability_record or self.sudo().search([('day','=',str(aware_now.date().isoweekday()))])) :
            duration = record.duration
            duration_offset = datetime.timedelta(hours=duration)
            spots = record.spots
            aware_today = aware_now.date() + datetime.timedelta(days=int(record.day)-aware_now.date().isoweekday())
            for i in range(5) :
                actual = aware_today + datetime.timedelta(weeks=i)
                if actual >= aware_now.date() :
                    start = record.start
                    end = record.end
                    unaware_starts = []
                    while start < end :
                        unaware_start = datetime.datetime.combine(actual, datetime.datetime.min.time())
                        unaware_start = unaware_start + datetime.timedelta(hours=start) - current_offset
                        unaware_starts.append(unaware_start)
                        start = start + duration
                        if start > end :
                            record.end = start
                    if not spot.search([('professional_id','=',record.professional_id.id), ('date','=',str(actual))]) :
                        for unaware_start in unaware_starts :
                            spot.create({'professional_id': record.professional_id.id,
                                         'date': str(actual),
                                         'start': str(unaware_start),
                                         'end': str(unaware_start + duration_offset),
                                         'spots': spots})
    
    @api.model
    def create(self, values) :
        res = super(PlannerProfessionalAvailability, self).create(values)
        self.spot_creation(availability_record=res)
        return res

class PlannerPlanner(models.Model) :
    _name = 'planner.planner'
    _description = 'Planner'
    
    def _get_default_timezone(self) :
        return DEFAULT_TIMEZONE
    
    name = fields.Char(string='Planner', readonly=True, copy=False, default='/')
    state = fields.Selection(string='Status', required=True, readonly=True, copy=False, tracking=True, default='planned',
                             selection=[('planned','Planned'),('received','Received'),('attended','Attended'),('cancel','Cancelled')])
    received = fields.Boolean(string='Received', compute='_compute_state', store=True, readonly=False)
    attended = fields.Boolean(string='Attended', compute='_compute_state', store=True)
    patient_id = fields.Many2one(comodel_name='res.partner', string='Patient', required=True)
    professional_id = fields.Many2one(comodel_name='planner.professional', string='Professional', required=True)
    procedure_ids = fields.Many2many(comodel_name='product.product', string='Procedures', compute='_compute_professional_id', store=True)
    procedure_id = fields.Many2one(comodel_name='product.product', string='Procedure', required=True)
    spot_id = fields.Many2one(comodel_name='planner.spot', string='Spot', domain=[('available_spots','>',0)])
    date = fields.Date(string='Date', compute='_compute_spot_id', store=True, readonly=True)
    start = fields.Datetime(string='Start', compute='_compute_spot_id', store=True, readonly=True)
    end = fields.Datetime(string='End', compute='_compute_spot_id', store=True, readonly=True)
    
    def receive_patient(self) :
        for record in self.filtered(lambda r: r.state=='planned') :
            record.state = 'received'
    
    def mark_attended(self) :
        for record in self.filtered(lambda r: r.state=='received') :
            record.state = 'attended'
    
    def mark_cancel(self) :
        for record in self.filtered(lambda r: r.state not in ['attended','cancel']) :
            record.state = 'cancel'
    
    def unlink(self) :
        attended = self.filtered(lambda r: r.attended)
        attended.mark_cancel()
        res = super(PlannerPlanner, self - attended).unlink()
        return res
    
    def write(self, values) :
        res = super(PlannerPlanner, self).write(values)
        if values.get('received') :
            self.filtered(lambda r: r.state=='planned').receive_patient()
        return res
    
    @api.depends('state')
    def _compute_state(self) :
        for record in self :
            if record.state == 'received' and not record.received :
                record.received = True
            if record.state == 'attended' and not record.attended :
                record.attended = True
    
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
