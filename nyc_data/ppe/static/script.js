var searchParams = new URLSearchParams(window.location.search);

function addUrlParameter(name, value) {
    searchParams.set(name, value);
    window.location.search = searchParams.toString();
}

$(function(){

    // Rollup Toggle
    if($('#rollup-options.toggle').length > 0){
        $('#rollup-options.toggle a').click(function(e){
            e.preventDefault();
            // Get intended url parameter and set it on the current url
            // to prevent blowing away sort options
            var parms = $(this).attr('href').split('?')[1].split('=');
            addUrlParameter(parms[0], parms[1]);
        });

        $('#rollup-options.toggle li a').each(function(){
            var searchParams = new URLSearchParams(window.location.search);
            var parms = $(this).attr('href').split('?')[1].split('=');
            if(searchParams.has(parms[0])) {
                if(searchParams.get(parms[0]) == parms[1]){
                    $(this).parent().addClass('active');
                } else {
                    $(this).parent().removeClass('active');
                }
            }
        });
    }


    // Datepicker
    if($('#reportrange').length > 0){
        $(function() {
            var start, end;

            start = searchParams.get('start_date') ? moment(searchParams.get('start_date')) : moment();
            end = searchParams.get('end_date') ? moment(searchParams.get('end_date')) : moment().add(29, 'days');
        
            function cb(start, end) {
                var newloc;

                $('#reportrange span').html(start.format('MMM D') + ' – ' + end.format('MMM D'));
                searchParams.set('start_date', start.format('YYYY-MM-DD'));
                searchParams.set('end_date', end.format('YYYY-MM-DD'));

                newloc = searchParams.toString();
                if (newloc != window.location.search.replace('?','')) {
                    window.location.search = newloc;
                }
            }
            $('#reportrange').daterangepicker({
                startDate: start,
                endDate: end,
                ranges: {
                    'This Week': [moment().startOf('week'), moment().endOf('week')],
                    'Next Week': [moment().add(1, 'week').startOf('week'), moment().add(1, 'week').endOf('week')],
                    'Next 7 Days': [moment(), moment().add(6, 'days')],
                    'Next 30 Days': [moment(), moment().add(29, 'days')],
                    'This Month': [moment().startOf('month'), moment().endOf('month')],
                    'Next Month': [moment().add(1, 'month').startOf('month'), moment().add(1, 'month').endOf('month')]
                }
            }, cb);
    
            cb(start, end);
        });
    }
        
    // Data staleness indicators
    if($('.dashboard-table').length > 0){
        $('th.tooltip').each(function(index) {
            var day, days, daystring;
            var matches = $(this).attr('aria-label').match(/\[(.*?)\]/);
            if(matches && matches[1] != 'None') {
                daystring = matches[1].replace(/-/g,'');
                day = moment(daystring);
                days = moment().diff(day, 'days');
                console.log($(this), days);
                if (days > 3) {
                    $(this).addClass('error');
                    $(this).find('a').after(svgClock);
                } else if (days > 1) {
                    $(this).addClass('warning');
                    $(this).find('a').after(svgClock);
                } 
            } 
        });
    }
});

svgClock = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><path d="M256 8a248 248 0 100 496 248 248 0 000-496zm0 448a200 200 0 110-400 200 200 0 010 400zm62-104l-85-62c-3-2-5-6-5-10V116c0-7 5-12 12-12h32c7 0 12 5 12 12v142l67 48c5 4 6 12 2 17l-18 26c-4 5-12 7-17 3z"/></svg>'