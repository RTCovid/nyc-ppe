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

            start = searchParams.get('start_date') ? moment(searchParams.get('start_date')) : moment().add(1, 'week').startOf('week');
            end = searchParams.get('end_date') ? moment(searchParams.get('end_date')) : moment().add(1, 'week').endOf('week');
        
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

    // Supply data column configuration
    if($('.dashboard-table').length > 0){
        var enabledSupply = searchParams.get('supply') ? searchParams.get('supply').split(',') : [];
        var allSupply = [];
        var disabledSupply = [];

        $('.supply-col').find('a').after(svgGear);
        $('th[data-supply-col]').each(function(){
            allSupply.push($(this).attr('data-supply-col'));
        });

        disabledSupply = [...allSupply].filter(x => !enabledSupply.includes(x));

        if (enabledSupply.length) {
            if (disabledSupply.length) {
                // Mute disabled columns
                for (var disabledColumn of disabledSupply) {
                    $(`[data-supply-col=${disabledColumn}]`).addClass('disabled');
                }
                $('.supply-col').addClass('active');
            }

            if(enabledSupply.length && enabledSupply.length != allSupply.length) {
                $('.supply-col svg').addClass('active');
            }
        }

        $('.supply-col svg').after(`<div class="supply-controls"><h3>Include in supply:</h3><ul></ul></div>`);
        for (col of allSupply) {
            if (!enabledSupply.length || enabledSupply.includes(col)) {
                $('.supply-controls ul').append(`<li><input type="checkbox" checked="checked" value="${col}" />${col}</li>`);
            } else {
                $('.supply-controls ul').append(`<li><input type="checkbox" value="${col}" />${col}</li>`);
            }
        }
        $('.supply-controls ul').append('<button>Change</button>')

        $('.supply-col svg').click(function(){ $('.supply-controls').toggle(); });
        $('.supply-controls button').click(function(){
            var newSupply = [];
            $('.supply-controls li input').each(function(){
                if ($(this).is(':checked')) {
                    newSupply.push($(this).attr('value'));
                }
            });
            addUrlParameter('supply', newSupply.join(','));
        });
    }
});

svgClock = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><path d="M256 8a248 248 0 100 496 248 248 0 000-496zm0 448a200 200 0 110-400 200 200 0 010 400zm62-104l-85-62c-3-2-5-6-5-10V116c0-7 5-12 12-12h32c7 0 12 5 12 12v142l67 48c5 4 6 12 2 17l-18 26c-4 5-12 7-17 3z"/></svg>';
svgGear = '<svg class="settings" viewBox="0 0 72 72" xmlns="http://www.w3.org/2000/svg"><path d="M71.754 28.773h-8.21c-4.381 0-5.431-2.535-2.334-5.631l5.807-5.806a.25.25 0 000-.349l-5.539-5.539a7059.707 7059.707 0 01-5.539-5.538.248.248 0 00-.348 0c-.096.097-2.707 2.709-5.805 5.806s-5.631 2.048-5.631-2.332v-8.21a.246.246 0 00-.246-.246H28.243a.246.246 0 00-.246.246v8.21c0 4.38-2.533 5.429-5.631 2.332L16.56 5.91a.248.248 0 00-.348 0c-.095.097-2.588 2.589-5.538 5.538l-5.539 5.539a.247.247 0 000 .349l5.805 5.806c3.098 3.096 2.048 5.631-2.332 5.631H.397a.247.247 0 00-.246.247v15.665c0 .135.111.246.246.246h8.209c4.381 0 5.43 2.534 2.334 5.631l-5.805 5.804a.247.247 0 000 .349l5.538 5.539 5.539 5.539a.246.246 0 00.348 0c.095-.097 2.709-2.709 5.805-5.806 3.099-3.097 5.632-2.047 5.632 2.332v8.211c0 .136.111.246.246.246h15.666c.135 0 .246-.11.246-.246v-8.211c0-4.379 2.533-5.429 5.631-2.333l5.806 5.806a.246.246 0 00.348 0c.095-.097 2.588-2.589 5.538-5.539l5.539-5.538a.25.25 0 000-.349l-5.805-5.804c-3.097-3.097-2.047-5.631 2.333-5.631h8.209a.246.246 0 00.246-.246v-7.833-7.832a.247.247 0 00-.246-.247zm-35.14 19.893c-6.663 0-12.064-5.4-12.064-12.063s5.401-12.065 12.064-12.065c6.662 0 12.065 5.402 12.065 12.065 0 6.663-5.403 12.063-12.065 12.063z" fill="#000" fill-rule="evenodd"/></svg>';